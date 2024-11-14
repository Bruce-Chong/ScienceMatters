import streamlit as st
import requests

if st.session_state.authenticated:

    # API URL
    api_url = "http://orionone1.pythonanywhere.com/annotate_pdf"
    #api_url = "http://orionone1.pythonanywhere.com/"

    # Streamlit App
    st.title("Orion One API")

    # File uploader
    uploaded_file = st.file_uploader("Choose a PDF file", type='pdf')

    if uploaded_file is not None:

        #pdf_path = r"C:\Users\CCHON1\PycharmProjects\SMdoc\2021 P5 Science SA2 Maha Bodhi filled.pdf"

        ## Send PDF file to API
        #file = {"file": ('2021 P5 Science SA2 Maha Bodhi filled.pdf',open('C:/Users/CCHON1/PycharmProjects/SMdoc/2021 P5 Science SA2 Maha Bodhi filled.pdf', 'rb'),'application/pdf')}

        # Reset file position to beginning
        uploaded_file.seek(0)

        # Send PDF file to API
        file = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
        headers = {"Content-Type": "multipart/form-data"}
        #response = requests.post(api_url, files=file, headers=headers)
        response = requests.post(api_url, files=file)

        # Check if API response is successful
        if response.status_code == 200:
            # Get annotated PDF from API response
            annotated_pdf = response.content

            # Display download button
            st.download_button("Download Annotated PDF", data=annotated_pdf, file_name="annotated.pdf", mime="application/pdf")

        else:
            st.error(f"Failed. Please try again. {response.content}")
    else:
        st.info("Please upload a PDF file to annotate.")

else:
    # Prompt for login
    st.warning("Please log in first before using SM AI-Tutor.")
