import streamlit as st

def report_view_component(report: str):
    st.subheader("Generated Financial Report")
    st.text_area(
        "Investment Report",
        report,
        height=400
    )
