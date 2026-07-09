import chainlit as cl
import google.generativeai as genai
import os

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

@cl.on_chat_start
async def start():
    # Initialize a clean session history with a system instruction
    cl.user_session.set("history", [
        {"role": "user", "parts": ["You are Orion, my ultimate personal assistant. Be concise, sharp, and helpful."]},
        {"role": "model", "parts": ["Understood. Orion online. How can I help you today?"]}
    ])
    await cl.Message(content="Orion initialized. Ready to assist.").send()

@cl.on_message
async def main(message: cl.Message):
    history = cl.user_session.get("history")
    
    # Append the user's new message
    history.append({"role": "user", "parts": [message.content]})
    
    # Generate response using the full conversation history for context
    response = model.generate_content(history)
    
    # Append model's response to maintain persistent short-term memory
    history.append({"role": "model", "parts": [response.text]})
    cl.user_session.set("history", history)
    
    await cl.Message(content=response.text).send()
