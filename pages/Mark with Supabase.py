import streamlit as st
import pdfplumber
from PIL import Image
from PyPDF2 import PdfReader
import pytesseract
import io
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import BaseTool
import re
import supabase
from langchain_core.messages import HumanMessage
import os
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


def extract_questions_and_answers(text):
    """
    Extract multiple question-answer pairs from the text.
    Assumes questions are in the format 'Question XX(y): ZZZZ' and answers follow as 'Answer XX(y): ZZZZ'.
    """
    # Pattern for Question and Answer extraction
    pattern = re.compile(r"Question\s(\d+\([a-zA-Z]\))\s*:\s*(.*?)\s*Answer\s\1\s*:\s*(.*?)\s*(?=Question|$)", re.S)

    matches = pattern.findall(text)

    # Create a list of dictionaries for each match
    extracted_data = []
    for match in matches:
        question_number = match[0]  # XX(y)
        question = match[1].strip()  # Question text
        answer = match[2].strip()  # Answer text

        extracted_data.append({
            "question_number": question_number,
            "question": question,
            "answer": answer
        })

    return extracted_data


# Tool to fetch relevant answers from Supabase (for Assistant)
def superbase_fetch(question_number):
    # Fetch question and model answer from Supabase
    response = supabase_client.table("QAScience_Papers").select("*").eq("question_number", question_number).execute()
    #response = supabase_client.table("QAScience_Papers").select("*").execute()
    #st.write(f'question_number is {question_number}suprabase result is {response}')
    if len(response.data) > 0:
        question = response.data[0].get("question")
        model_answer = response.data[0].get("answer")
        marks = response.data[0].get("marks")
        return {
            "question": question,
            "model_answer": model_answer,
            "marks": marks
        }
    else:
        return {"error": f"Model answer not found for {question_number}."}

# Initialize Researcher agent and Assistant agent

class TeacherTool(BaseTool):
    name = "TeacherTool"
    description = "Compares user answer with the model answer and awards marks."

    def _run(self, user_answer: str, model_answer: str, marks: int) -> str:
        # Simple comparison logic to check correctness and assign marks
        if user_answer.strip().lower() == model_answer.strip().lower():
            return f"Correct! You have been awarded {marks} marks."
        else:
            return f"Incorrect. The correct answer was '{model_answer}'. You receive 0 marks."


# Initialize the Teacher Tool
teacher_tool = TeacherTool()

# Create a Teacher agent using LangChain's React agent
llm_teacher = ChatOpenAI(model="gpt-4o-mini", temperature=0)
teacher_agent = create_react_agent(llm_teacher, tools=[teacher_tool])

# OCR and text extraction from PDF
# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        # Try extracting text from the PDF
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        return str(e)


# Function to perform OCR on an image-based PDF
def ocr_pdf(pdf_file):
    text = ""
    reader = PdfReader(pdf_file)
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        if '/Image' in page['/Resources']:
            # Extract images from PDF page
            page_images = page['/Resources']['/Image']
            for img_name, img in page_images.items():
                image_data = img.get_data()
                image = Image.open(io.BytesIO(image_data))
                text += pytesseract.image_to_string(image)
    return text


# Function to retrieve and grade multiple questions
def retrieve_and_grade_multiple_questions(question_answer_pairs):
    results = []
    config = {"configurable": {"thread_id": "abc123"}}

    for qa_pair in question_answer_pairs:
        question_number = qa_pair["question_number"]
        user_answer = qa_pair["answer"]

        # Fetches model answer from Supabase
        answer_result = superbase_fetch(question_number)

        if "error" in answer_result:
            results.append({"question_number": question_number, "result":  answer_result["error"]})
            continue

        model_answer = answer_result.get("model_answer")
        marks = answer_result.get("marks")

        messages = [
            {"role": "user", "content": user_answer},
            {"role": "assistant", "content": model_answer},  # Optionally the agent's previous response
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

    # Option 2: Upload PDF
    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

    if uploaded_file is not None:
        config = {"configurable": {"thread_id": "abc123"}}
        # Extract text from the uploaded PDF using OCR
        extracted_text = extract_text_from_pdf(uploaded_file)
        if not extracted_text:
            extracted_text = ocr_pdf(uploaded_file)

        # Display extracted text
        st.write("Extracted Text from PDF:")
        #st.write(extracted_text)

        if st.button("Grade Answers"):
            # Step 1: Researcher agent extracts multiple questions and answers
            question_answer_pairs = extract_questions_and_answers(extracted_text)

            if not question_answer_pairs:
                st.write("No questions found in the document.")
            else:
                # Step 2: Process each question-answer pair
                #st.write(question_answer_pairs)
                grading_results = retrieve_and_grade_multiple_questions(question_answer_pairs)

                #st.write(f'grading results is {grading_results}')

                # Step 3: Display results
                for result in grading_results:
                    st.write(f"Question: {result['question_number']}")
                    st.write(f"Your Answer: {result['user_answer']}")
                    st.write(f"Model Answer: {result['model_answer']}")
                    st.write(f"Grading: {result['grading_result']}")

else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")

