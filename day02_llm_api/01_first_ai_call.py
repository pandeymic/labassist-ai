import os
from dotenv import load_dotenv
from groq import Groq

# 1. Load secret API keys from ~/.env automatically
load_dotenv(os.path.expanduser("~/.env"))

def ask_groq(question):

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": question}]
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    test_question = "What are the 3 most common blood tests ordered in a diagnostic lab? Explain in 2 sentences."
    print("Sending question to Groq AI...")
    
    answer = ask_groq(test_question)
    
    print("\n--- AI Response ---")
    print(answer)
    print("-------------------")
