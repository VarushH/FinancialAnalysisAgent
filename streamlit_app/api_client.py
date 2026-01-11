import requests
from streamlit_app.config import API_BASE_URL

def start_session(session_id: str, pdf_path: str):
    return requests.post(
        f"{API_BASE_URL}/start",
        json={
            "session_id": session_id,
            "input": {
                "pdf_path": pdf_path
            }
        }
    ).json()

def get_session_state(session_id: str):
    return requests.get(
        f"{API_BASE_URL}/state/{session_id}"
    ).json()

def approve_report(session_id: str, approved: bool, comments: str):
    return requests.post(
        f"{API_BASE_URL}/approve",
        json={
            "session_id": session_id,
            "approved": approved,
            "comments": comments
        }
    ).json()
