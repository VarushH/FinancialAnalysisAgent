#A simple compliance checker that looks for forbidden terms. It flags any occurrences of words like "fraud", "illicit", etc. In a real app, this could integrate legal rules or an ML model.

# backend/agents/compliance.py
def process(pages, send_message):
    send_message("Compliance checking started")
    text = " ".join(pages).lower()
    forbidden = ['fraud', 'bribery', 'kickback', 'illegal', 'sanction']
    found = [word for word in forbidden if word in text]
    if found:
        result = f"Potential compliance issues found: {', '.join(found)}."
    else:
        result = "No immediate compliance issues detected."
    send_message("Compliance checking completed")
    return result
