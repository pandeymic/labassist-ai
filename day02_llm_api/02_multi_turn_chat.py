import os
from dotenv import load_dotenv
from groq import Groq

# 1. Load API keys from ~/.env
load_dotenv(os.path.expanduser("~/.env"))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 2. How AI Memory Works:
# AI models are stateless — they forget everything instantly!
# To give LabAssist "memory", we keep a list of ALL messages in the conversation.
# Notice the 3 roles:
# - "system": Instructions that tell the AI how to behave (personality, rules).
# - "user": What the patient types.
# - "assistant": What the AI replies.

messages = [
    {
        "role": "system",
        "content": "You are LabAssist, a friendly and accurate medical laboratory assistant. Keep your answers brief (2-3 sentences) and helpful."
    }
]

def chat_step(user_message):
    # Step A: Append the user's new message to our conversation history list
    messages.append({"role": "user", "content": user_message})

    # Step B: Send the ENTIRE messages list (with all history) to Groq
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    ai_reply = response.choices[0].message.content

    # Step C: Append the AI's reply to our conversation history so it remembers next time!
    messages.append({"role": "assistant", "content": ai_reply})

    return ai_reply


if __name__ == "__main__":
    print("=== Welcome to LabAssist AI Chat ===")
    print("Type 'exit' to quit.\n")

    while True:
        # Get input from the user in terminal
        user_text = input("Patient: ")

        if user_text.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        # Get reply from AI with memory
        reply = chat_step(user_text)
        print(f"LabAssist: {reply}\n")
