
import streamlit as st
from PIL import Image
import streamlit as st
import bcrypt
from dotenv import load_dotenv
import os

# Load environment variables
#load_dotenv("./env/dev.env")
load_dotenv()
st.set_page_config(page_title='Science Matters')

logo=Image.open('Logo.png')
# Retrieve credentials from environment variables
USERID = os.getenv("USERID")
PASSWORD_HASH = os.getenv("PASSWORD_HASH").encode('utf-8')

# Initialize session state for authentication if it doesn't exist
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def main():
    if not st.session_state.authenticated:
        login()
    else:
        pages()

def login():
    st.subheader("Please Log In")

    username = st.text_input("User ID")
    password = st.text_input("Password", type="password")

    if st.button("Log In"):
        if username == USERID and bcrypt.checkpw(password.encode('utf-8'), PASSWORD_HASH):
            st.session_state.authenticated = True
            st.success("Login successful!")
            st.rerun
        else:
            st.error("Invalid username or password. Please try again.")

def pages():
    c1, c2 = st.columns([0.9, 3.2])
    with c1:
        st.caption('')
    with c2:
        st.image(logo, width=300)
        st.title('   Science Matters:'
                 'An AI-Enhanced Tutor')
    #st.sidebar.title("Navigation")
    #page = st.sidebar.selectbox("Select a page:", ["Introduction", "CrewAI with Rag", "LLC RAG"])

    #if page == "Introduction":
        st.write("# Introduction")
        st.write("Welcome to our Science Matters AI Chatbot Research Hub!")
        st.write("Use our menu to explore and optimize the retrieval of specific content using various advanced methods, with a focus on identifying the most accurate and efficient approaches. Leveraging Retrieval-Augmented Generation (RAG), we test and compare:")
        st.write("Dense Retrieval: Deep learning models for context matching.")
        st.write("Sparse Retrieval: Traditional keyword matching.")
        st.write("Hybrid Retrieval: Combining dense and sparse strengths.")
        st.write("Knowledge Graphs: Using structured data for precision.")
        st.write("Our Approach")
        st.write("We collect diverse data, implement various retrieval methods, and evaluate their performance based on accuracy, response time, and user satisfaction. Our findings drive continuous improvement in AI chatbot technology.")
    #elif page == "Page 2":
        #st.write("# Welcome to Page 2")
        #st.write("Content for Page 2 goes here.")
    #elif page == "Page 3":
        #st.write("# Welcome to Page 3")
        #st.write("Content for Page 3 goes here.")

if __name__ == "__main__":
    main()

