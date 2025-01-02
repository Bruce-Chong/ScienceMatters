import streamlit as st
from supabase import create_client
from openai import OpenAI
import os
import pymupdf
import pandas as pd

# Initialize Supabase client for storing model answers
url = os.getenv("SUPABASE_URL")
supa_api_key = os.getenv("SUPABASE_API_KEY")
supabase_client = create_client(url, supa_api_key)

# OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")


# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_text = []
    with pymupdf.open(stream=pdf_file.read(), filetype="pdf") as doc:
        for page in doc:
            pdf_text.append(page.get_text())
    return "\n".join(pdf_text)


# Function to send extracted text to OpenAI
def process_text_with_openai(extracted_text):
    prompt = (
        "Extract the questions from the following test paper text. "
        "For multiple-choice questions, include only the question number, question and marks allocated. Named this question type as MCQ "
        "For open-ended questions, include the question number, question, answer and marks allocated. Name this question type as OEQ"
        "Output each question in a row, with this sequence, 1. question type, 2. question number, 3. question, 4. answer, 5.marks. Do not numbered the rows"
        "Separate each column with ||\n\n"
        f"{extracted_text}"
    )

    client = OpenAI()


    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content


# Streamlit layout
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if st.session_state.authenticated:
    st.title("Transfer Paper to DB")
    #st.subheader("PDF must be OCRed and saved with text. This program takes the pdf and extracts text, classifying questions. For MCQ, only questions are captured. For OEQ, both questions and answers are captured.")
    st.text("PDF must be OCRed and saved with text. This program takes the pdf and extracts text, ")
    st.text("classifying questions. For MCQ, only questions are captured.")
    st.text("For OEQ, both questions and answers are captured.")
    st.text("Need to add level and paper name before inserting into Supabase")

    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"], key="pdfform")

    if uploaded_file and st.button("Extract content from paper"):
        with st.spinner("Processing the PDF..."):
            # Extract text from uploaded PDF
            extracted_text = extract_text_from_pdf(uploaded_file)

            # Process text with OpenAI
            try:
                processed_data = process_text_with_openai(extracted_text)
                st.success("Data successfully retrieved from OpenAI!")
                #st.write(processed_data)

                # Convert OpenAI response to DataFrame
                rows = []
                for line in processed_data.split("\n"):
                    parts = line.split("||")  # Assuming OpenAI response is structured
                    if len(parts) == 5:  # Question number, question, answer
                        rows.append({"Q type": parts[0].strip(),
                                     "Q No": parts[1].strip(),
                                     "Question": parts[2].strip(),
                                     "Answer": parts[3].strip(),
                                     "Marks": parts[4].strip()})
                    elif len(parts) == 4:  # Question number, question only
                        rows.append({"Q type": parts[0].strip(),
                                     "Q No": parts[1].strip(),
                                     "Question": parts[2].strip(),
                                     "Marks": parts[3].strip()})

                df = pd.DataFrame(rows)
                st.dataframe(df)

                # Store the data in Supabase
                #supabase_client.table("test_paper_questions").insert(rows).execute()
                #st.success("Data stored in the database!")
            except Exception as e:
                st.error(f"Error processing data: {str(e)}")

else:
    st.warning("Please log in first before using SM AI-Tutor.")
