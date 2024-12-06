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

def annotate_pdf(pdf_file, grading_results):
    # Load the PDF document from the in-memory BytesIO object
    pdf_document = pymupdf.open("pdf", pdf_file.read())

    # Step 3: Iterate through fields and add annotations
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]

        # Retrieve form fields (interactive elements) on the page
        widgets = page.widgets()

        #check if this page has drawings
        draw_df = mark_df[(mark_df['pageno'] == page_num) & (mark_df['type'] == "IMG")]

        if widgets:
            # Get the position of the form field
            for widget in widgets:
                field_rect = widget.rect
                field_name = widget.field_name
                # Define the annotation position next to the form field

                temp_df = mark_df.loc[mark_df['question_number'] == str(field_name), ['grade', 'type']]
                if not temp_df.empty:
                    print(f"inside temp df for question {field_name}")
                    result_row = temp_df.iloc[0]
                    annotation_text = result_row['grade']
                    question_type = result_row['type']
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
                else:
                    # Handle the case where no rows match the condition
                    result_row = None
                    print(f"No matching rows for question_number: {field_name}")

        #check if there are drawings
        for index, row in draw_df.iterrows():
            grade = row['grade']
            rect = row['rect']
            annotation_rect = pymupdf.Rect(
                rect.x0,  # Offset to place annotation next to field
               rect.y1,
                rect.x1,
                rect.y1 + 100
            )
            page.insert_textbox(annotation_rect, grade, fontsize=8, color=(1, 0, 0))

    #output_path = r"C:\Users\Choon Yong Chong\PycharmProjects\SMContentWriter\pdf\annotated_pdf.pdf"
    dir_path = os.path.dirname(os.path.realpath(__file__))
    output_path = os.path.join(dir_path, 'annotated_pdf.pdf')
    pdf_document.save(output_path)

    # Display the modified PDF
    st.download_button("Download Marked PDF", data=open(output_path, "rb"), file_name="annotated_pdf.pdf")


def extract_answers(pdf_file):
    # Create a PdfReader object
    pdf_reader = pypdf.PdfReader(pdf_file)
    # Access the form fields
    fields = pdf_reader.get_fields()

    if fields:
        # Create the DataFrame using list comprehensions
        df = pd.DataFrame({
            "question_number": [str(field_name) for field_name in fields.keys()],
            "answer": [str(field_value.get('/V', '').strip()) for field_value in fields.values()]
        })
    else:
        print("No form fields found in the PDF.")
        return None

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
    mark_match = re.search(r"Score:\s*(\d+)", grade)
    marks_awarded = int(mark_match.group(1)) if mark_match else None
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
def retrieve_and_grade_multiple_questions(paper, qa_df, pdf_file):
    results = []
    doc = pymupdf.open("pdf", pdf_file.read())

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

        elif question_type == "IMG":
            for page_num in range(len(doc)):
                # Get the page
                page = doc.load_page(page_num)
                search_top = question_number + " Please draw within box"
                search_bottom = "box end " + question_number
                rect_top = page.search_for(search_top)
                rect_bottom = page.search_for(search_bottom)
                if rect_top:
                    # set the coordinates of the rectangle
                    img_rect = pymupdf.Rect(rect_top[0].x0, rect_top[0].y1, rect_bottom[0].x1, rect_bottom[0].y0)
                    # Get the image of the page
                    pix = page.get_pixmap(clip=img_rect)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.save(f"{page_num}.png")
                    # Covert to base64
                    imgbuffered = BytesIO()
                    img.save(imgbuffered, format="PNG")  # Save image to BytesIO buffer in JPEG format (or any format you need)
                    img_bytes = imgbuffered.getvalue()  # Get the bytes of the image

                    # Encode the image bytes to base64
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                    #set the prompt
                    img_prompt = f"""
                                Analyse this image using built in vision and grade it according to marking guidelines and provide a score out of {marks}. 
                                Additionally, provide short and concise feedback ONLY if the answer is wrong or partially right.
    
                                ### Marking Guidelines:
                                {model_answer}
    
                                ### Image:
                                [Image Attached]
    
                                ### Instructions:
                                Award marks out of {marks} based on the accuracy, completeness of the Image according to the marking guidelines.
                                Provide the score in the standard format like 'Score: 2 marks'. 
                                Give short and concise feedback for improvement only if the score is below full marks.
                                        """

                    grading_result = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": img_prompt,
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{img_base64}"
                                        },
                                    },
                                ],
                            }
                        ],
                    )
                    grade = grading_result.choices[0].message.content
                    packed_answer.grading_result = grade
                    packed_answer.page_num = page_num
                    results = update_results(results, grade, packed_answer, img_rect)


        elif user_answer == None:
            packed_answer.grading_result = "No answer, 0 marks"
            add_question(packed_answer, xrect)
        elif user_answer.strip() == "":
            packed_answer.grading_result = "No answer, 0 marks"
            add_question(packed_answer, xrect)

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
                                model="gpt-4o-mini",
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

    doc.close()
    return results

if st.session_state.authenticated:
    # Streamlit layout
    st.title("PDF Question Answer Grader with Assistant Agent")

    #st.text_input("Enter prompt for AI", value=st.session_state.prompt, key="prompt" )
    #st.text_input("Teacher Agent Description", value=st.session_state.teachdes, key="teach")
    st.text_input("AI model", value=st.session_state.aimodel, key="ai")
    st.number_input("AI temperature from 0(strict) to 1(creative)", value=st.session_state.temperature, key="temp")

    # Option 2: Upload PDF
    uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"], key="pdfform")

    if uploaded_file is not None:

        read_file = io.BytesIO(uploaded_file.read())
        #config = {"configurable": {"thread_id": "abc123"}}
        # Display extracted text
        paper_title = extract_paper(uploaded_file)
        st.write(f"Paper: {paper_title} submitted!")

        if st.button("Grade Answers"):
            # Step 1: Extract all form data from pdf
            question_answer_pairs = extract_answers(uploaded_file)
            #st.dataframe(question_answer_pairs)

            # Step 2: Extract answer
            retrieve_and_grade_multiple_questions(paper_title, question_answer_pairs,read_file)

            st.dataframe(mark_df)
            read_file.seek(0)
            annotate_pdf(read_file, mark_df)

else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")


