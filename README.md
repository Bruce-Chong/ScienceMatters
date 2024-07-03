This AI chatbot uses crewAI for agents acting as a science teacher to create an agentic workflow, using streamlit as web interface. 
Process: 
  1. Get user input/question
  2. Send input to crew of agents to process
  3. Agent(science teacher) uses RAG to search directory for PDFs to find relevant data
  4. Agent replies
  5. User may continue to chat/ask question with AI
  6. Repeat step 1 with chat history as context.
AI FM: chatGPT3.5/4 depending on openAI key used.
