# /functions/pdf_utils.py

import pdfplumber
import re
import pymupdf
import os
import pandas as pd
import streamlit as st
import pypdf


# Extract paper serial number from pdf
def extract_paper_number(pdf_file):
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



# Extract student's answers from PDF
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



# Annotate the PDF with the grading results
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

