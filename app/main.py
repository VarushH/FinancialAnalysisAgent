# app/main.py
from app.workflow.financial_graph import financial_graph
from app.state.dynamodb import save_state, load_state

def handler(event, context):
    session_id = event["session_id"]
    state = load_state(session_id)

    state.update(event["input"])
    final_state = financial_graph.invoke(state)

    save_state(session_id, final_state)
    return final_state
