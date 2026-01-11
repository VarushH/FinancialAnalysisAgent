import streamlit as st
import tempfile
import os

def upload_component():
    st.subheader("Upload Financial Document")
    uploaded = st.file_uploader(
        "Upload PDF document",
        type=["pdf"]
    )

    if uploaded:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(uploaded.read())
        tmp.close()
        st.success("Document uploaded successfully")

        return tmp.name

    return None
