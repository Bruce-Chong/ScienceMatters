import streamlit as st
import pypdf
import pdfplumber
from openai import OpenAI
import langgraph
import re
import supabase
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os
import io
from io import BytesIO
from string import Template
import pymupdf
import pandas as pd
#error with streamlit hosting
#from langgraph.checkpoint.sqlite import SqliteSaver

#memory = SqliteSaver.from_conn_string(":memory:")

# Initialize OpenAI API
#api_key = os.getenv("OPENAI_KEYS")
#os.environ["OPENAI_API_KEY"] = api_key

# Set recursion limit
langgraph.recursion_limit = 50

mark_df = pd.DataFrame(columns=['question_number', 'marks'])

# Initialize Supabase client for fetching model answers
url = os.getenv("SUPABASE_URL")
supa_api_key = os.getenv("SUPABASE_API_KEY")
supabase_client = supabase.create_client(url, supa_api_key)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#Semantic comparison with language models
smodel = SentenceTransformer('all-MiniLM-L6-v2')

if "prompt" not in st.session_state:
    st.session_state.prompt = f'You are a Primary school science teacher marking students question paper. Compare their answer :$useranswer,  with the model answer :$modelanswer and the marking guide here: $aiprompt. Give marks according to the allocated marks here : $marks. Only give feedback if answer is partially correct or wrong, otherwise just say correct.'

if "teachdes" not in st.session_state:
    st.session_state.teachdes = "Compares user answer with the model answer and awards marks according to the marks given. Every comparison must have a conclusion, do not followup with a question"

if "aimodel" not in st.session_state:
    st.session_state.aimodel = "gpt-4o"

if "temperature" not in st.session_state:
    st.session_state.temperature = 0

# Function to add a row to the DataFrame
def add_question(question_number, marks):
    global mark_df
    new_row = pd.DataFrame({'question_number': [question_number], 'marks': [marks]})
    mark_df = pd.concat([mark_df, new_row], ignore_index=True)

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

# Function to get the grading_result for a specific question_number
def get_grading_result(grading_results, target_question_number):
    for result in grading_results:
        if result["question_number"] == target_question_number:
            return result["grading_result"], result["question_type"]
    return None  # Return None if the question_number is not found

def annotate_pdf(pdf_file, grading_results):
    # Load the PDF document from the in-memory BytesIO object
    pdf_document = pymupdf.open("pdf", pdf_file.read())

    # Embed the Wingdings font in the PDF
    fontname = 'ZapfDingbats'

    # Step 3: Iterate through fields and add annotations
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]

        # Retrieve form fields (interactive elements) on the page
        widgets = page.widgets()

        if widgets:
            # Get the position of the form field
            for widget in widgets:
                field_rect = widget.rect
                field_name = widget.field_name
                field_value = widget.field_value
                # Define the annotation position next to the form field

                result = get_grading_result(grading_results, field_name)
                annotation_text = result[0]
                question_type = result[1]
                if question_type == 'MCQ':
                    annotation_rect = pymupdf.Rect(
                        field_rect.x1 + 10,  # Offset to place annotation next to field
                        field_rect.y0,
                        field_rect.x1 + 50,
                        field_rect.y1 + 50
                    )
                else:
                    annotation_rect = pymupdf.Rect(
                        field_rect.x0,  # Offset to place annotation next to field
                        field_rect.y1,
                        field_rect.x1,
                        field_rect.y1 + 100
                    )


                page.insert_textbox(annotation_rect, annotation_text, fontsize=8, color=(1, 0, 0))

            # Save the modified PDF to display the change
            # Save the modified PDF
    output_path = r"C:\Users\Choon Yong Chong\PycharmProjects\SMContentWriter\pdf\annotated_pdf.pdf"
    pdf_document.save(output_path)

    # Display the modified PDF
    st.download_button("Download Marked PDF", data=open(output_path, "rb"), file_name="annotated_pdf.pdf")


def extract_answers(pdf_file):
    # Create a PdfReader object
    pdf_reader = pypdf.PdfReader(pdf_file)
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



# Function to retrieve and grade multiple questions
def retrieve_and_grade_multiple_questions(paper, question_answer_pairs):
    results = []

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

        #print(f"question number is h{question_number}h and question type is h{question_type}h")
        if question_type == "MCQ":
            if user_answer == str(model_answer):
                grade = "Correct. 2 marks"
                gmarks = 2
                add_question(question_number, gmarks)
            else:
                grade = f"Wrong. Answer is {str(model_answer)}. 0 marks"
                gmarks = 0
                add_question(question_number, gmarks)
            results.append({
                "question_number": question_number,
                "question_type": question_type,
                "user_answer": user_answer,
                "model_answer": model_answer,
                "grading_result": grade,
                "gmarks": gmarks
            })
        elif user_answer.strip() == "":
            add_question(question_number, 0)
            results.append({
                "question_number": question_number,
                "question_type": question_type,
                "user_answer": user_answer,
                "model_answer": model_answer,
                "grading_result": "No answer, 0 marks",
                "gmarks": 0
            })
        else:
            messages = f"""
                    Based on the following guidelines, compare the user's answer to the model answer and provide a score out of {marks}. 
                    Additionally, provide short and concise feedback ONLY if answer is wrong or partially right.
                    ### Marking Guidelines:
                    {aiprompt}
                    
                    ### Model Answer:
                    {model_answer}
                
                    ### User's Answer:
                    {user_answer}
                
                    ### Instructions:
                    Award marks out of {marks} based on the accuracy in standard format like 'Score: 2 marks', completeness, and clarity of the user's answer compared to the model answer. 
                    Give short and concise feedback for improvement only if the score is below full marks.
                    """

            grading_result = client.chat.completions.create(
                                model=st.session_state.aimodel,
                                messages=[
                                    {"role": "system", "content": "You are a Primary school science teacher marking student answers."},
                                    {"role": "user", "content": messages}
                                ],
                                max_tokens=1500,
                                temperature=0
                            )


            grade = grading_result.choices[0].message.content



            # Use regex to parse out the awarded marks and feedback
            mark_match = re.search(r"Score:\s*(\d+)", grade)
            marks_awarded = int(mark_match.group(1)) if mark_match else None
            add_question(question_number, marks_awarded)

            # Find the position of "Feedback:" and get the text after it
            if "Feedback:" in grade:
                # Find the text after "Feedback:"
                feedback = grade.split("Feedback:", 1)[1].strip()
                feedback = feedback + f" {marks_awarded} marks"
            else:
                feedback = f"Correct. {marks_awarded} marks"

            print(f"question number is {question_number} and feedback is {feedback}. {marks_awarded} marks")

            results.append({
                "question_number": question_number,
                "question_type": question_type,
                "user_answer": user_answer,
                "model_answer": model_answer,
                "grading_result": feedback,
                "gmarks": marks_awarded
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

        annotate_file = io.BytesIO(uploaded_file.read())
        config = {"configurable": {"thread_id": "abc123"}}
        # Display extracted text
        paper_title = extract_paper(uploaded_file)
        st.write(f"Paper: {paper_title} submitted!")

        if st.button("Grade Answers"):
            # Step 1: Researcher agent extracts multiple questions and answers
            question_answer_pairs = extract_answers(uploaded_file)

            if not question_answer_pairs:
                st.write("No questions found in the document.")
            else:
                # Step 2: Process each question-answer pair
                grading_results = retrieve_and_grade_multiple_questions(paper_title, question_answer_pairs)

                st.dataframe(mark_df)
                #make changes here!
                annotate_pdf(annotate_file, grading_results)


else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")


