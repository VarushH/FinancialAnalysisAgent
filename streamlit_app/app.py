import streamlit as st
import time

from streamlit_app.state import get_session_id
from streamlit_app.api_client import start_session, get_session_state
from streamlit_app.components.upload import upload_component
from streamlit_app.components.status import status_component
from streamlit_app.components.report_view import report_view_component
from streamlit_app.components.approval import approval_component
from streamlit_app.config import POLL_INTERVAL

st.set_page_config(
    page_title="Enterprise Financial Analysis",
    layout="wide"
)

st.title("📊 Financial Analysis Multi-Agent System")

session_id = get_session_id()

pdf_path = upload_component()

if pdf_path:
    start_session(session_id, pdf_path)
    st.info("Agent workflow started")

state_placeholder = st.empty()

while True:
    state = get_session_state(session_id)

    with state_placeholder.container():
        status_component(state)

        if "report" in state:
            report_view_component(state["report"])
            approval_component(session_id)
            break

    time.sleep(POLL_INTERVAL)