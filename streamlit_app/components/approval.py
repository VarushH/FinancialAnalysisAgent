import streamlit as st
from streamlit_app.api_client import approve_report

def approval_component(session_id: str):
    st.subheader("Human Approval")

    comments = st.text_area("Approval comments / audit notes")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Approve Report"):
            approve_report(session_id, True, comments)
            st.success("Report approved successfully")

    with col2:
        if st.button("Reject Report"):
            approve_report(session_id, False, comments)
            st.error("Report rejected and sent back to supervisor")
