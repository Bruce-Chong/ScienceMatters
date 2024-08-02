import os

from langchain.tools.retriever import create_retriever_tool
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from PyPDF2 import PdfReader


# Third-party modules
import streamlit as st
from PIL import Image


# Setting environment variables for keys (if any required by the tools)
# OpenAI API Key Input

logo=Image.open('Logo.png')
# Initialize session state for authentication if it doesn't exist
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Initialize session state for RAG documents if it doesn't exist
if "rag" not in st.session_state:
    st.session_state.rag = ""

# Initialize session state for agents if it doesn't exist
if "teachagent" not in st.session_state:
    st.session_state.teachagent = ""

# Initialize session state for agents if it doesn't exist
if "agentdes" not in st.session_state:
    st.session_state.agentdes = "search the documents and answer the question from user."

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

# Define a function to create a DirectoryLoader for a specific file type
def create_directory_loader(file_type, directory_path):
    loaders = {
        '.pdf': PyPDFLoader,
        '.docx': Docx2txtLoader,
    }
    return DirectoryLoader(
        path=directory_path,
        glob=f"**/*{file_type}",
        loader_cls=loaders[file_type],
    )
def loading():
    st.subheader("Please input RAG setup")
    pdf_docs = st.file_uploader("Upload PDF files, multiple files accepted:👇",
                                accept_multiple_files=True, key="pdf_uploader")
    st.session_state.agentdes = st.text_input("Agent description👇", value=st.session_state.agentdes)

    if st.button("Start RAGGING!"):
        try:
            st.session_state.rag = pdf_docs

            main()
            return True
        except RuntimeError as error:
            st.error(error)
            return False

def main():
    memory = SqliteSaver.from_conn_string(":memory:")
    raw_text = get_pdf_text(st.session_state.rag)
    text_chunks = get_text_chunks(raw_text)
    vectorstore = get_vector_store(text_chunks, api_key)
    retriever = vectorstore.as_retriever()
    tool = create_retriever_tool(
                retriever,
            "science_teacher",
                st.session_state.agentdes,
                )
    #tools = [tool]
    tools=[]
    st.session_state.teachagent = create_react_agent(llm, tools, checkpointer=memory)


if st.session_state.authenticated:
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GEMINI_KEY")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.3, google_api_key=api_key)
    memory = SqliteSaver.from_conn_string(":memory:")

    config = {"configurable": {"thread_id": "abc123"}}

    logo = Image.open('Logo.png')
    c1, c2 = st.columns([0.9, 3.2])
    with c1:
        st.caption('')
    with c2:
        st.image(logo, width=300)
        st.title('   Science Matters:'
                 'An AI-Enhanced Tutor')

    # RAG Function Description
    rag_description = """Langchain and Langgraph(Agentic workflow) and openAI Test
    """
    st.markdown(rag_description)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if loading():
        st.success("Ragging done!")
    st.subheader('Q&A record with SM AI-Tutor')
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)

    if user_input := st.chat_input("Welcome and ask a question to the AI tutor"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("agent", avatar='👨🏻‍🏫'):
            message_placeholder = st.empty()
            with st.spinner('Thinking...'):
                response = st.session_state.teachagent.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
                for m in response['messages']:
                    message_placeholder.markdown(m.content)

                agent_reply = response["messages"][-1]
                st.session_state.messages.append({"role": "assistant", "content": agent_reply.content})


else:
    # Prompt for API key if not entered
    st.warning("Please login to use SM AI-Tutor.")