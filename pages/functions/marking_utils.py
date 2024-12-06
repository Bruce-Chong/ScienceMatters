# /functions/marking_utils.py

import pandas as pd
import re

# Adding rows to mark_df
def add_question(ans_set, rect):
    global mark_df
    new_row = pd.DataFrame({'question_number': [ans_set.question_number], 'marks': [ans_set.gmarks], 'grade': [ans_set.grading_result], 'type': [ans_set.question_type], 'rect': [rect], 'pageno': [ans_set.page_num]})
    mark_df = pd.concat([mark_df, new_row], ignore_index=True)

# Extract question number and student's answer from dataframe
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


def update_results(grade, packed_ans, rect):
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
