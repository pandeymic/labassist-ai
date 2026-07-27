import json
from typing import Dict, Any

def classify_intent(user_message: str, client: Any) -> Dict[str, str]:
    """
    Classifies the user's incoming message into one of 5 distinct diagnostic lab workflows:
    - BOOK_APPOINTMENT: Patient wants to book/schedule a laboratory test or home sample collection.
    - CHECK_PRICE_OR_INFO: Patient is asking about test prices, turnaround time, preparation, or medical purpose.
    - FAQ_OR_POLICY: Patient is asking about reports delivery, payment methods, or lab policies.
    - CANCEL_RESCHEDULE: Patient wants to cancel or reschedule an existing booking.
    - GENERAL_CHAT: Greeting, thank you, or off-topic conversational chit-chat.

    Returns a dict: {"intent": "<INTENT_NAME>", "confidence": "high", "reasoning": "..."}
    """
    system_prompt = (
        "You are an AI Intent Classifier for a medical diagnostic laboratory named LabAssist. "
        "Analyze the user's message and classify it into EXACTLY ONE of these 5 intents:\n"
        "1. BOOK_APPOINTMENT\n"
        "2. CHECK_PRICE_OR_INFO\n"
        "3. FAQ_OR_POLICY\n"
        "4. CANCEL_RESCHEDULE\n"
        "5. GENERAL_CHAT\n\n"
        "You MUST respond ONLY with a valid JSON object in this exact format:\n"
        '{"intent": "<INTENT_NAME>", "confidence": "high|medium|low", "reasoning": "brief explanation"}'
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        data = json.loads(response.choices[0].message.content)
        return data
    except Exception as e:
        # Fallback keyword classifier if API fails
        lower_msg = user_message.lower()
        if any(w in lower_msg for w in ["book", "schedule", "appointment", "home collection", "test for me"]):
            return {"intent": "BOOK_APPOINTMENT", "confidence": "medium", "reasoning": "Keyword match fallback"}
        elif any(w in lower_msg for w in ["cancel", "reschedule", "change time"]):
            return {"intent": "CANCEL_RESCHEDULE", "confidence": "medium", "reasoning": "Keyword match fallback"}
        elif any(w in lower_msg for w in ["price", "cost", "how much", "fasting", "what is"]):
            return {"intent": "CHECK_PRICE_OR_INFO", "confidence": "medium", "reasoning": "Keyword match fallback"}
        else:
            return {"intent": "GENERAL_CHAT", "confidence": "low", "reasoning": "Default fallback"}


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from groq import Groq

    load_dotenv(os.path.expanduser("~/.env"))
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    test_queries = [
        "Hi, I need to book a CBC test for tomorrow morning at my home",
        "How much is the lipid profile and do I need to fast?",
        "When will I get my reports on WhatsApp?",
        "Please cancel my appointment for tomorrow"
    ]

    for q in test_queries:
        res = classify_intent(q, client)
        print(f"Query: '{q}'\n -> Classified Intent: {res['intent']} ({res.get('reasoning', '')})\n")
