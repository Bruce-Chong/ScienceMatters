import bs4
from langchain.tools.retriever import create_retriever_tool
from langchain_chroma import Chroma
from langchain_community.document_loaders import WebBaseLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent
from langchain_google_vertexai import ChatVertexAI
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import os

# Third-party modules
import streamlit as st
from PIL import Image

logo=Image.open('Logo.png')
api_key = os.getenv("GEMINI_KEY")


def get_pdf_text(pdf_docs):
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=200)
    chunks = text_splitter.split_text(text)
    return chunks

def get_vector_store(text_chunks, api_key):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")
    return vector_store


def main():
    memory = SqliteSaver.from_conn_string(":memory:")
    n = 1
    x = 1
    tools = []
    teacher_agent = create_react_agent(llm, tools, checkpointer=memory)
    config = {"configurable": {"thread_id": "abc123"}}
    st.write(f"I am at main {x}")
    x = x + 1
    st.image(logo, width=300)
    st.title('Science Matters: An AI-Enhanced Tutor')
    # RAG Function Description
    rag_description = """Answer queries with uploaded document as context, using GEMINI-PRO LLM and Chroma as MIPS"""
    st.markdown(rag_description)
    st.subheader('Q&A record with SM AI-Tutor💁')


    with st.sidebar:
        st.title("Menu:")
        pdf_docs = st.file_uploader("Upload your PDF Files and Click on the Submit & Process Button",
                                    accept_multiple_files=True, key="pdf_uploader")
        if st.button("Submit & Process", key="process_button"):
            with st.spinner("Processing..."):
                raw_text = get_pdf_text(pdf_docs)
                text_chunks = get_text_chunks(raw_text)
                vectorstore = get_vector_store(text_chunks, api_key)
                retriever = vectorstore.as_retriever()
                tool = create_retriever_tool(
                    retriever,
                    "science teacher",
                    "search the documents and answer the question from user.",
                )
                tools = [tool]
                teacher_agent = create_react_agent(llm, tools, checkpointer=memory)
                st.write(f"Teacher agent create{n}")
                n = n + 1
                #teacher_agent = create_react_agent(llm, tools, checkpointer=memory)
                #config = {"configurable": {"thread_id": "abc123"}}
                st.success("Done")

    if user_input := st.chat_input("Welcome and ask a question to the AI tutor"):
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("agent", avatar='👨🏻‍🏫'):
            message_placeholder = st.empty()
            with st.spinner('Thinking...'):
                response = teacher_agent.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
                for m in response['messages']:
                    message_placeholder.markdown(m.content)

if st.session_state.authenticated:
    memory = SqliteSaver.from_conn_string(":memory:")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3, google_api_key=api_key)
    logo = Image.open('Logo.png')
    # Load environment variables
    load_dotenv("./env/dev.env")

    main()

else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")