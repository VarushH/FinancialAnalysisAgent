from langchain_google_genai import ChatGoogleGenerativeAI

def get_gemini():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=0.2,
        max_output_tokens=4096
    )
