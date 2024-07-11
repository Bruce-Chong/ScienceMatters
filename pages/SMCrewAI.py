import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import PDFSearchTool
import bcrypt
from dotenv import load_dotenv

# Third-party modules
import streamlit as st
from PIL import Image

# Initialize session state for authentication if it doesn't exist
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
# Setting environment variables for keys (if any required by the tools)


logo=Image.open('Logo.png')


if st.session_state.authenticated:
    # Load environment variables
    #load_dotenv("./env/dev.env")
    load_dotenv()
    api_key = os.getenv("OPENAI_KEY")
    os.environ["OPENAI_API_KEY"] = api_key
    # Define the tools
    pdf_search_tool = PDFSearchTool(pdf=f'{os.getcwd()}/downloads/Adaptation.pdf')


    # Define the science teacher agent
    science_teacher = Agent(
        role='Science Teacher',
        goal='Answer questions from Helpdesk Support using provided PDFs ',
        backstory=(
            "You are a knowledgeable and friendly science teacher with vast experience in teaching primary school science."           
            "You use the provided PDFs to find accurate answers to students' questions."
        ),
        tools=[pdf_search_tool],
        memory=True,
        verbose=True,
        max_iter=25,
        allow_delegation=False
    )

    # Define the task
    answer_science_questions_task = Task(
        description=(
            "Analyze if the question is a valid primary school science question"
            "Answer primary school science questions using the provided PDFs"
        ),
        expected_output='A detailed answer to the science question',
        tools=[pdf_search_tool],
        agent=science_teacher,
    )

    # Form the crew
    science_crew = Crew(
        agents=[science_teacher],
        tasks=[answer_science_questions_task],
        process=Process.sequential,
        memory=True
    )


    # Function to handle user interaction with continuity
    def ask_questions_with_continuity(zprompt):
            #question = input("Ask a science question (or type 'exit' to quit): ")
            #if question.lower() == 'exit':
                #print("Goodbye!")
                #break

            #conversation_history.append({"role": "user", "content": question})
            inputs = {
                'question': zprompt,
                'conversation_history': st.session_state.messages
            }

            result = science_crew.kickoff(inputs=inputs)
            st.session_state.messages.append({"role": "assistant", "content": result})

            return result


    # Start the interactive loop
    #if __name__ == "__main__":
    #    ask_questions_with_continuity()



    c1, c2 = st.columns([0.9, 3.2])
    with c1:
        st.caption('')
    with c2:
        st.image(logo, width=300)
        st.title('   Science Matters:'
                 'An AI-Enhanced Tutor')

    # RAG Function Description
    rag_description = """Using a combination of CrewAI Agents(Agentic workflows) and RAG(Retrival-Augmented Generation) to provide contextually accurate and SM's unique answering technique to Singapore Primary School's Science queries. 
    """
    st.markdown(rag_description)

    st.subheader('Q&A record with SM AI-Tutor💁')
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)

    if prompt := st.chat_input("Welcome and ask a question to the AI tutor"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        #for message in st.session_state.messages:
            #with st.chat_message(message["role"]):
                #st.markdown(message["content"])
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("agent", avatar='👨🏻‍🏫'):
            message_placeholder = st.empty()
            with st.spinner('Thinking...'):
                message_placeholder.markdown(ask_questions_with_continuity(prompt))
else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")