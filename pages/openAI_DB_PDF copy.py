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
import base64
import pymupdf
import pandas as pd
from PIL import Image
from dataclasses import dataclass

# Define the dataclass
@dataclass
class Answer:
    question_number: str
    question_type: str
    user_answer: str
    model_answer: str
    grading_result: str
    gmarks: int
    page_num: int

xrect = pymupdf.Rect(0,0,0,0)

# Set recursion limit
langgraph.recursion_limit = 50

mark_df = pd.DataFrame(columns=['question_number', 'marks','type','grade','rect','pageno'])

# Initialize Supabase client for fetching model answers
url = os.getenv("SUPABASE_URL")
supa_api_key = os.getenv("SUPABASE_API_KEY")
supabase_client = supabase.create_client(url, supa_api_key)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#Semantic comparison with language models
smodel = SentenceTransformer('all-MiniLM-L6-v2')

if "aimodel" not in st.session_state:
    st.session_state.aimodel = "gpt-4o"

if "temperature" not in st.session_state:
    st.session_state.temperature = 0

# Function to add a row to the DataFrame
def add_question(ans_set, rect):
    global mark_df
    new_row = pd.DataFrame({'question_number': [ans_set.question_number], 'marks': [ans_set.gmarks], 'grade': [ans_set.grading_result], 'type': [ans_set.question_type], 'rect': [rect], 'pageno': [ans_set.page_num]})
    mark_df = pd.concat([mark_df, new_row], ignore_index=True)

def extract_paper(pdf_file):
    paper = "CHS2021P5SA2"
    return paper

def extract_answers(uploaded_file):
    """
    Parses a CSV file to extract question numbers and answers, filling blanks with 'null',
    and returns a DataFrame with two columns: 'question_number' and 'answer'.

    Parameters:
        file_path (str): The path to the CSV file.

    Returns:
        pd.DataFrame: A DataFrame with two columns: 'question_number' and 'answer'.
    """
    try:
        # Attempt to read the CSV file
        raw_data = pd.read_csv(uploaded_file, header=None)
    #except FileNotFoundError:
    #    raise FileNotFoundError(f"The file at '{file_path}' was not found. Please check the file path.")
    except pd.errors.EmptyDataError:
        raise ValueError("The file is empty. Please provide a valid CSV file with data.")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred while reading the file: {e}")

    try:
        # Ensure the file has at least two columns
        if raw_data.shape[1] < 2:
            raise ValueError("The CSV file must contain at least two columns for question numbers and answers.")

        # Extract the first column as question numbers and the second column as answers
        question_data = raw_data.iloc[:, [0, 1]]
        question_data.columns = ["question_number", "answer"]

        # Fill missing answers with "null"
        question_data["answer"] = question_data["answer"].fillna("null")

        # Reset the index
        df = question_data.reset_index(drop=True)
    except KeyError:
        raise KeyError("Error in column selection. Ensure the file has sufficient columns.")
    except Exception as e:
        raise ValueError(f"An error occurred while processing the data: {e}")

    return df


def get_answer(question_number, dataframe, indexed=False):
    if indexed:
        try:
            answer = dataframe.loc[question_number, 'answer']
            if isinstance(answer, pd.Series):
                return answer.tolist()
            return answer
        except KeyError:
            return None
    else:
        filtered = dataframe.loc[dataframe['question_number'] == question_number, 'answer']
        if not filtered.empty:
            if len(filtered) > 1:
                return filtered.tolist()
            return filtered.iloc[0]
        return None

# Tool to fetch relevant answers from Supabase (for Assistant)
def superbase_fetch(paper):
    # Fetch question and model answer from Supabase
    response = supabase_client.table("QAScience_Papers").select("*").eq("paper", paper).execute()

    return response.data

def update_results(res, grade,packed_ans, rect):
    # Use regex to parse out the awarded marks and feedback
    mark_match = re.search(r"Score:\s*(\d+(\.\d+)?)", grade)   #changed regex to capture decimal places
    marks_awarded = mark_match.group(1) if mark_match else None
    packed_ans.gmarks = marks_awarded


    # Find the position of "Feedback:" and get the text after it
    if "Feedback:" in grade:
        # Find the text after "Feedback:"
        feedback = grade.split("Feedback:", 1)[1].strip()
        feedback = feedback + f" {marks_awarded} marks"
    else:
        feedback = f"{grade} {marks_awarded} marks"

    packed_ans.grading_result = feedback,
    packed_ans.gmarks = marks_awarded

    add_question(packed_ans, rect)


# Function to retrieve and grade multiple questions
def retrieve_and_grade_multiple_questions(paper, qa_df):
    results = []
    #doc = pymupdf.open("pdf", pdf_file.read()) #no need to annotate PDF file

    #Step 1 fetch answers from Supabase
    db_data = superbase_fetch(paper)
    if "error" in db_data:
        results.append({"Paper": paper, "result": db_data["error"]})

    for row in db_data:

        question_number = row["question_number"]
        user_answer = get_answer(question_number, qa_df)
        model_answer = row["answer"]
        marks =row["marks"]
        question_type =row["question_type"]
        aiprompt =row["prompt"]

        packed_answer = Answer(
            question_number=question_number,
            question_type=question_type,
            user_answer=user_answer,
            model_answer=model_answer,
            grading_result="",
            gmarks=0,
            page_num=0
        )

        if question_type == "MCQ":
            if user_answer == str(model_answer):
                packed_answer.grading_result = "Correct. 2 marks"
                packed_answer.gmarks = 2
                add_question(packed_answer, xrect)
            else:
                packed_answer.grading_result = f"Wrong. Answer is {str(model_answer)}. 0 marks"
                packed_answer.gmarks = 0
                add_question(packed_answer, xrect)

        #deleted the case for IMG

        elif user_answer == None:
            packed_answer.grading_result = "No answer, 0 marks"
            add_question(packed_answer, xrect)
        elif user_answer.strip() == "":
            packed_answer.grading_result = "No answer, 0 marks"
            add_question(packed_answer, xrect)

        else:
            messages = f"""
               You are an examiner grading elementary-level science exam responses. Your grading must strictly follow the given model answers and the specified scoring rules. Do not deviate from the model answers. 
               Base all partial credit on how closely the student's response matches or aligns with these model answers.
               
               ### Model Answer:
               {model_answer}
    
               ### Student's Answer:
               {user_answer}

               ### Maximum marks for each question:
               {marks}

               ###Scoring Guidelines:
               Each question has a maximum mark (e.g., 2 marks per question, or as specified).
               Award marks in increments of 0.5.
               Only award full marks if the response matches the model answer closely in both content and scientific accuracy.
               If the response is partially correct, award partial marks in increments of 0.5. If the answer is completely off or irrelevant, award 0 marks.
               If the student’s response includes extraneous, incorrect, or misleading information that contradicts the model answer, reduce marks accordingly.
               Student's response has to be very precise in the use of scientific terms. For example, mentioning "air" to indicate "water vapour in the air" is incorrect. Penalize at least 0.5 marks for such errors.
               Penalize wrong scientific terms or concepts. For example, "the temperature of water gains heat..." is incorrect because temperature is not a substance that can gain heat. It should be "the water gains heat...". Penalize at least 0.5 marks for such errors.
               Always expect an explicit answer, and the marker should not infer or assume any information that is not explicitly stated in the student's response. For example, "oxygen is carried through the body" is incorrect if the student did not mention "blood" as the carrier. Penalize at least 0.5 marks for such errors.
               Only give full marks if the student's response is complete, accurate, precise and scientfically correct. If the student's response is incomplete, award partial marks based on the completeness and accuracy of the response.

               ### Instructions:
               For each question, consider the marks given to the student's answer in a step-by-step manner.
               First, look at the model answer and the maximum marks for the question. Marks are given in 0.5 increments.
               Second, determine the key points in the model answer and decide how many marks to award for each point, in increments of 0.5. For example, for a question with 2 key points of roughly equal importance, assign 0.5 marks to each. Another example - for a question that has 2 entities/phrases in the model answer, assign 0.5 marks to each.
               In determining the key points, do take note of key scientific terms and descriptions, or certain actions that are given in the model answer. Be very precise in the concepts and scientific terms. For example, air is not the same as water vapour, and vice versa.
               Third, compare the student's answer to the model answer, and award marks for the question in standard format like 'Score: 2 marks' in increments of 0.5. Ensure you provide the final marks for each question in the standard format. You should award marks based on the completeness and clarity of the student's answer compared to the model answer. The marks assgined MUST be equal or lower than the maximum marks for the question.
               Fourth, do not penalize for spelling or grammatical errors. Only consider the scientific accuracy and completeness of the answer. It is important that the student uses the right words to capture the correct scientific concept.
               Fifth, provide short and concise feedback ONLY if answer is wrong or partially right.

                ###Examples on how to award marks:

               ##Example 1:
               Question: There is an image showing many butterfly eggs laid on the egg. Explain how laying many eggs each time helps the butterfly in their survival.
               Model answer: To increase the chances of some eggs hatching into young which will develop into adults that can reproduce to ensure the continuity of their kind.
               Maximum marks: 1
               Student's answer: To have more chances for the eggs to hatch into butterflies.
               Scoring guidelines: 
               - This question has a maximum of 1 marks.
               - The two key points, of which each point is worth 0.5 marks, are: "increasing chances of some eggs hatching into young" and "ensuring the continuity of their kind".
                - The student's answer only covers the first key point, so award 0.5 marks.
                - Score: 0.5 marks

                ##Example 2:
                Question: There is an image showing how an electircal circuit can be opened and closed through the closing and opening of a door respectively, and thus ringing a bell. Explain how the bell would ring when Peter pushed the door open.
                Model answer: When the door was opened, The copper strip attached to the door will touch the other copper strip to form a closed circuit.
                Maximum marks: 2
                Student's answer: When the copper strip on the door touch the other copper strip, the circuit becomes a closed circuit and electric current can flow thorugh to ring the bell.
                Scoring guidelines:
                - This question has a maximum of 2 marks.
                - There are 3 key points: "When the door was opened" which describes the required action to close the circuit. "The copper strip attached to the door will touch the other copper strip" which describes the closing of the circuit. "form a closed circuit" which describes the completion of the circuit, and where the phrase closed circuit is the key here.
                - The student's answer did not mention the action of the door being opened, but covered the other two key points on the concept of a closed circuit.
                - Delete 0.5 marks for the minor omission of the door being opened, and award 1.5 marks for the other two key points.
                - Score: 1.5 marks

               """

            grading_result = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": "You are a Primary school science teacher marking student answers."},
                                    {"role": "user", "content": messages}
                                ],
                                max_tokens=1500,
                                temperature=0
                            )


            grade = grading_result.choices[0].message.content
            packed_answer.grading_result = grade
            results = update_results(results, grade, packed_answer, xrect)

    #doc.close()
    return results

## instructions_4 prompt
# messages = f"""
#                Be an elementary science school teacher ready to mark and score a student's answer.
#                Based on the following guidelines, compare the student's answer to the model answer and provide a score out of {marks}. 
               
#                ### Model Answer:
#                {model_answer}
    
#                ### Student's Answer:
#                {user_answer}

#                ### Maximum marks for each question:
#                {marks}
    
#                ### Instructions:
#                For each question, consider the marks given to the student's answer in a step-by-step manner.
#                First, look at the model answer and the maximum marks for the question. Marks are given in 0.5 increments.
#                Second, determine the key points in the model answer and decide how many marks to award for each point, in increments of 0.5. For example, for a question with 2 key points of roughly equal importance, assign 0.5 marks to each. Another example - for a question that has 2 entities/phrases in the model answer, assign 0.5 marks to each.
#                In determining the key points, do take note of key scientific terms and descriptions, or certain actions that are given in the model answer. Be very precise in the concepts and scientific terms. For example, air is not the same as water vapour, and vice versa.
#                Third, compare the student's answer to the model answer, and award marks for the question in standard format like 'Score: 2 marks' in increments of 0.5. Ensure you provide the final marks for each question in the standard format. You should award marks based on the completeness and clarity of the student's answer compared to the model answer. The marks assgined MUST be equal or lower than the maximum marks for the question.
#                Fourth, do not penalize for spelling or grammatical errors. Only consider the scientific accuracy and completeness of the answer. It is important that the student uses the right words to capture the correct scientific concept.
#                Fifth, provide short and concise feedback ONLY if answer is wrong or partially right.
#                """


if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if st.session_state.authenticated:
    # Streamlit layout
    st.title("PDF Question Answer Grader with Assistant Agent")

    #st.text_input("Enter prompt for AI", value=st.session_state.prompt, key="prompt" )
    #st.text_input("Teacher Agent Description", value=st.session_state.teachdes, key="teach")
    st.text_input("AI model", value=st.session_state.aimodel, key="ai")
    st.number_input("AI temperature from 0(strict) to 1(creative)", value=st.session_state.temperature, key="temp")

    # Option 2: Upload PDF
    uploaded_file = st.file_uploader("Upload a CSV file with question number and student's answer", type=["csv"])

    if uploaded_file is not None:

        #read_file = io.BytesIO(uploaded_file.read())
        #config = {"configurable": {"thread_id": "abc123"}}
        # Display extracted text
        paper_title = extract_paper(uploaded_file)
        st.write(f"Paper: {paper_title} submitted!")

        if st.button("Grade Answers"):
            # Step 1: Extract all form data from pdf
            question_answer_pairs = extract_answers(uploaded_file)
            #st.dataframe(question_answer_pairs)

            # Step 2: Extract answer
            retrieve_and_grade_multiple_questions(paper_title, question_answer_pairs)

            st.dataframe(mark_df)
            #read_file.seek(0)
            #annotate_pdf(read_file, mark_df)

else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")


