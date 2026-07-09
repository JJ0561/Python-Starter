import chainlit as cl
import google.generativeai as genai
import os
import sqlite3

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize the database
conn = sqlite3.connect('orion_memory.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_fact TEXT
    )
''')
conn.commit()


def get_long_term_memory():
    cursor.execute('SELECT user_fact FROM memory')
    facts = cursor.fetchall()
    if not facts:
        return ""
    memory_string = "Here are some things you should remember about me:\n"
    for fact in facts:
        memory_string += f"- {fact[0]}\n"
    return memory_string


@cl.on_chat_start
async def start():
    long_term_memory = get_long_term_memory()

    system_prompt = "You are Orion, my ultimate personal assistant. Be concise, sharp, and helpful."
    if long_term_memory:
        system_prompt += f"\n\n{long_term_memory}"

    cl.user_session.set("history", [
        {"role": "user", "parts": [system_prompt]},
        {"role": "model", "parts": ["Understood. Orion online. How can I help you today?"]}
    ])
    await cl.Message(content="Orion initialized. Ready to assist.").send()


@cl.on_message
async def main(message: cl.Message):
    history = cl.user_session.get("history")

    history.append({"role": "user", "parts": [message.content]})

    response = model.generate_content(history)

    history.append({"role": "model", "parts": [response.text]})
    cl.user_session.set("history", history)

    await cl.Message(content=response.text).send()
