import streamlit as st

def status_component(state: dict):
    st.subheader("Agent Execution Status")

    steps = [
        "extracted_data",
        "financial_analysis",
        "compliance",
        "risk",
        "report"
    ]

    for step in steps:
        if step in state:
            st.success(f"✅ {step.replace('_', ' ').title()} completed")
        else:
            st.warning(f"⏳ {step.replace('_', ' ').title()} pending")
