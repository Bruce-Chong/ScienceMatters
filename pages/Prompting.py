import streamlit as st
import supabase
from openai import OpenAI
import os
import sys
# Initialize Supabase client for fetching model answers
url = os.getenv("SUPABASE_URL")
supa_api_key = os.getenv("SUPABASE_API_KEY")
supabase_client = supabase.create_client(url, supa_api_key)

def generate_marking_guide(answer):
    # Define the prompt with the provided answer
    prompt = f"""
    As an expert science teacher, create a concise marking guide for the following correct answer:

    "{answer}"

    Include:
    - Key points and concepts expected in a student's answer.
    - Essential scientific terms that demonstrate understanding.
    - Criteria for assessing explanation depth and accuracy.
    - Common mistakes to watch for.

    Provide the guide in clear, brief bullet points suitable for evaluating student responses.
    """
    client = OpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    # Call the OpenAI API with the prompt
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                ],
            }
        ],
)

    # Extract the response text
    #print(response.choices[0].message.content)
    return response.choices[0].message.content.strip()

if st.session_state.authenticated:
    # Streamlit layout
    st.title("Generate prompt to DB using agent")

    paper = st.text_input("Enter the paper title to generate or regenerate prompt", value="MBPS2021P5SA2")

    if st.button("Generate prompt"):
        # Initialize the Supabase client
        supabase_client = supabase.create_client(url, supa_api_key)

        try:
            # Fetch the 'answer' column from 'QAScience_Papers' table
            response = supabase_client.table('QAScience_Papers').select('answer', "id").eq("paper", paper).eq("question_type", "OEQ").execute()

            # Check if the request was successful
            if len(response.data) > 0:
                data = response.data
                for idx, item in enumerate(data):
                    answer = item['answer']
                    record_id = item['id']
                    # Generate the customized prompt using the chain
                    custom_prompt = generate_marking_guide(answer)
                    try:
                        # Save the generated prompt back to the Supabase table under 'prompt' column

                        update_response = supabase_client.table('QAScience_Papers').update({'prompt': custom_prompt}).eq('id', record_id).execute()
                        print(f"Response is {update_response}")
                        #print(f"Marking Guide for question {question_number}, Answer {idx + 1}:\n{custom_prompt}\n{'-' * 50}\n")
                    except Exception as e:
                        print(f"Failed to update to Supabase: {e}")
                        sys.exit()
            else:
                print("Error fetching data:", response.error)

        except Exception as e:
            print("An error occurred:", e)
else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")


