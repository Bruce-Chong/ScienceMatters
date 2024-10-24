import streamlit as st
import PyPDF2
import pdfplumber
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import BaseTool
import re
import supabase
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os
from string import Template
#error with streamlit hosting
#from langgraph.checkpoint.sqlite import SqliteSaver

#memory = SqliteSaver.from_conn_string(":memory:")

# Initialize OpenAI API
#api_key = os.getenv("OPENAI_KEYS")
#os.environ["OPENAI_API_KEY"] = api_key

# Initialize Supabase client for fetching model answers
url = os.getenv("SUPABASE_URL")
supa_api_key = os.getenv("SUPABASE_API_KEY")
supabase_client = supabase.create_client(url, supa_api_key)

#Semantic comparison with language models
smodel = SentenceTransformer('all-MiniLM-L6-v2')

if "prompt" not in st.session_state:
    st.session_state.prompt = f'You are a Primary school science teacher marking students question paper. Compare their answer :$useranswer,  with the model answer :$modelanswer and the marking guide here: $aiprompt. Give feedback and allocate marks $marks accordingly'

if "teachdes" not in st.session_state:
    st.session_state.teachdes = "Compares user answer with the model answer and awards marks according to the marks given. Every comparison must have a conclusion, do not followup with a question"

if "aimodel" not in st.session_state:
    st.session_state.aimodel = "gpt-4o-mini"

if "temperature" not in st.session_state:
    st.session_state.temperature = 0

def extract_paper(pdf_file):
    text = ""
    try:
        # Try extracting text from the PDF
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + " "

        #st.write(f"text is {text}")
        match = re.search(r'Paper_no: (\w+)', text)
        if match:
            return match.group(1)  # Return the word found after "Paper_no:"
        else:
            return None  # Return None if no match is found

    except Exception as e:
        return str(e)
def extract_answers(pdf_file):
    # Create a PdfReader object
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    # Access the form fields
    fields = pdf_reader.get_fields()

    # Check if the PDF contains any form fields
    if fields:
        extracted_data = []
        for field_name, field_value in fields.items():
            question_number = field_name
            answer = field_value.get('/V').strip()
            extracted_data.append({
                "question_number": str(question_number),
                "answer": str(answer)
            })

        # Custom sorting key to handle numeric and subsection formatting
        def sorting_key(q_num):
            # Regular expression to capture numeric and letter components
            # The key idea is to split numeric and non-numeric parts correctly
            parts = re.split(r'(\d+)', q_num["question_number"])
            # Convert numeric parts to integers, leave others as strings
            return [int(part) if part.isdigit() else part for part in parts]

        # Sort the extracted data based on the custom sorting key
        extracted_data.sort(key=sorting_key, reverse=False)  # Ensure ascending order
    else:
        print("No form fields found in the PDF.")

    return extracted_data

# Tool to fetch relevant answers from Supabase (for Assistant)
def superbase_fetch(paper, question_number):
    # Fetch question and model answer from Supabase
    response = supabase_client.table("QAScience_Papers").select("*").eq("question_number", question_number).eq("paper", paper).execute()
    #response = supabase_client.table("QAScience_Papers").select("*").execute()
    #st.write(f'question_number is {question_number}suprabase result is {response}')
    if len(response.data) > 0:
        question = response.data[0].get("question")
        model_answer = response.data[0].get("answer")
        marks = response.data[0].get("marks")
        question_type = response.data[0].get("question_type")
        return {
            "question": question,
            "question_type": question_type,
            "model_answer": model_answer,
            "marks": marks
        }
    else:
        return {
            "question": "Not found",
            "question_type": "Not found",
            "model_answer": "Not found",
            "marks": "Not found"
        }



class TeacherTool(BaseTool):
    #description = "Compares user answer with the model answer and awards marks according to the marks given. Every comparison must have a conclusion, do not followup with a question"
    name: str = "TeacherTool"
    description: str = st.session_state.teachdes

    def _run(self, user_answer: str, correct_answer: str, marks: int) -> str:
        # Simple comparison logic to check correctness and assign marks proportionally
        user_embedding = smodel.encode(user_answer)
        model_embedding = smodel.encode(correct_answer)
        similarity = cosine_similarity([user_embedding], [model_embedding])[0][0]

        #print(f'the user_answer is {user_answer} and the marks is {marks} ')
        # Initialize awarded marks
        awarded_marks = 0

        # Award marks based on similarity
        if similarity >= 0.8:  # Full marks if similarity is above 80%
            awarded_marks = marks
        elif similarity > 0.5:  # Partial marks if similarity is between 50-80%
            awarded_marks = round(similarity * marks)  # Scale marks proportionally

        # Ensure awarded marks do not exceed total_marks (important step)
        awarded_marks = min(awarded_marks, marks)

        # Return the appropriate message
        if similarity >= 0.8:
            return f"Correct! You have been awarded {awarded_marks} marks."
        elif similarity > 0.5:
            return f"Partially correct. You have been awarded {awarded_marks} marks."
        else:
            return f"Incorrect. The correct answer was '{correct_answer}'. You receive {awarded_marks} marks."


# Initialize the Teacher Tool
teacher_tool = TeacherTool()

# Create a Teacher agent using LangChain's React agent
#llm_teacher = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_teacher = ChatOpenAI(model=st.session_state.aimodel, temperature=st.session_state.temperature)
teacher_agent = create_react_agent(llm_teacher, tools=[teacher_tool])


# Function to retrieve and grade multiple questions
def retrieve_and_grade_multiple_questions(paper, question_answer_pairs):
    results = []
    config = {"configurable": {"thread_id": "abc123"}}

    sorted_list = sorted(question_answer_pairs, key=lambda x: x['question_number'])

    for qa_pair in sorted_list:
        question_number = qa_pair["question_number"]
        user_answer = qa_pair["answer"]

        # Fetches model answer from Supabase
        answer_result = superbase_fetch(paper,question_number)

        if "error" in answer_result:
            results.append({"question_number": question_number, "result":  answer_result["error"]})
            continue

        model_answer = answer_result.get("model_answer")
        marks = answer_result.get("marks")
        question_type = answer_result.get("question_type")
        aiprompt = answer_result.get("prompt")

        print(f"question number is h{question_number}h and question type is h{question_type}h")
        if question_type == "MCQ":
            if user_answer == str(model_answer):
                grade = "Correct. 2 marks"
            else:
                grade = "Wrong. 0 marks"

            results.append({
                "question_number": question_number,
                "user_answer": user_answer,
                "model_answer": model_answer,
                "grading_result": grade
            })
        else:
            #minput = f'You are a Primary school science teacher marking students question paper. Compare their answer :{user_answer},  with the model answer :{model_answer} ,give feedback and allocate marks {marks} accordingly'
            temp_obj = Template(st.session_state.prompt)
            minput = temp_obj.substitute(useranswer=user_answer, modelanswer=model_answer, aiprompt=aiprompt, marks=marks)
            messages = [
                {"role": "user", "content": minput}
            ]
            # Teacher agent grades the user's answer

            grading_result = teacher_agent.invoke({
                "user_answer": user_answer,
                "correct_answer": model_answer,
                "marks": marks,
                "messages": messages  # Include the entire conversation history
            }, config=config)

            grade = ''
            for m in grading_result['messages']:
                grade = m.content

            results.append({
                "question_number": question_number,
                "user_answer": user_answer,
                "model_answer": model_answer,
                "grading_result": grade
            })

    return results

if st.session_state.authenticated:
    # Streamlit layout
    st.title("PDF Question Answer Grader with Assistant Agent")


    st.text_input("Enter prompt for AI", value=st.session_state.prompt, key="prompt" )
    st.text_input("Teacher Agent Description", value=st.session_state.teachdes, key="teach")
    st.text_input("AI model", value=st.session_state.aimodel, key="ai")
    st.number_input("AI temperature from 0(strict) to 1(creative)", value=st.session_state.temperature, key="temp")

    # Option 2: Upload PDF
    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"], key="pdfform")

    if uploaded_file is not None:
        config = {"configurable": {"thread_id": "abc123"}}
        # Display extracted text
        paper_title = extract_paper(uploaded_file)
        st.write(f"Paper: {paper_title} submitted!")
        #st.write(extracted_text)

        if st.button("Grade Answers"):
            # Step 1: Researcher agent extracts multiple questions and answers
            question_answer_pairs = extract_answers(uploaded_file)

            if not question_answer_pairs:
                st.write("No questions found in the document.")
            else:
                # Step 2: Process each question-answer pair
                #st.write(question_answer_pairs)
                grading_results = retrieve_and_grade_multiple_questions(paper_title, question_answer_pairs)

                #st.write(f'grading results is {grading_results}')

                # Step 3: Display results
                for result in grading_results:
                    try:
                        st.write(f"Question: {result['question_number']}")
                        st.write(f"Your Answer: {result['user_answer']}")
                        st.write(f"Model Answer: {result['model_answer']}")
                        st.write(f"Grading: {result['grading_result']}")
                    except:
                        st.write(f"Question: {result['question_number']}")
                        st.write(f"Your Answer: Not answered")
                        st.write(f"Model Answer: {result['model_answer']}")
                        st.write(f"Grading: {result['grading_result']}")
else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")


