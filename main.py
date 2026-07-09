import asyncio
import sqlite3
import os

import chainlit as cl
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize the database
conn = sqlite3.connect('orion_memory.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        user_fact TEXT,
        UNIQUE(username, user_fact)
    )
''')
# Migrate existing table: add username column if it doesn't exist yet
try:
    cursor.execute('ALTER TABLE memory ADD COLUMN username TEXT')
except sqlite3.OperationalError:
    pass  # Column already exists
conn.commit()


def get_long_term_memory(username: str) -> str:
    cursor.execute(
        'SELECT user_fact FROM memory WHERE username = ?', (username,)
    )
    facts = cursor.fetchall()
    if not facts:
        return ""
    lines = "\n".join(f"- {fact[0]}" for fact in facts)
    return f"Here are some things you should remember about me:\n{lines}"


async def extract_and_save_fact(username: str, user_message: str):
    """Use Gemini to detect and save a memorable personal fact from the user's message."""
    extraction_prompt = f"""
    Analyze this message from {username}.
    Does it contain a permanent fact, preference, relationship, or important detail about them that a personal assistant should remember forever?
    Message: "{user_message}"

    If YES, output ONLY the concise fact (e.g. "User's favorite color is blue." or "User has a dog named Max.").
    If NO, output exactly "NONE".
    """
    try:
        response = await model.generate_content_async(extraction_prompt)
        fact = response.text.strip()
        if fact and fact != "NONE":
            cursor.execute(
                'INSERT INTO memory (username, user_fact) VALUES (?, ?)', (username, fact)
            )
            conn.commit()
            print(f"Background Memory Saved for {username}: {fact}")
    except Exception as e:
        print(f"Background extraction failed: {e}")


@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    family_accounts = {
        "JJ": "admin123",
        "Mom": "family",
        "Brother": "family",
        "Sister": "family",
    }
    if username in family_accounts and family_accounts[username] == password:
        return cl.User(identifier=username)
    return None


@cl.on_chat_start
async def start():
    user = cl.user_session.get("user")
    username = user.identifier
    cl.user_session.set("username", username)

    if username == "JJ":
        # God mode: full read access to the entire family database
        cursor.execute('SELECT username, user_fact FROM memory')
        all_facts = cursor.fetchall()

        system_instruction = "You are JJ's Master Assistant. You have full read/write access to the entire family's database.\n"
        if all_facts:
            system_instruction += "Here is the current family database context:\n"
            for fact in all_facts:
                system_instruction += f"- {fact[0]}'s data: {fact[1]}\n"

        cl.user_session.set("history", [
            {"role": "user", "parts": [system_instruction]},
            {"role": "model", "parts": ["Master privileges acknowledged. I am ready to manage the family fleet."]}
        ])
        await cl.Message(content=f"Welcome back, Commander **{username}**. Master access granted. I can see the whole family's data.").send()

    else:
        # Sandboxed mode: only this user's facts
        cursor.execute('SELECT user_fact FROM memory WHERE username = ?', (username,))
        user_facts = cursor.fetchall()

        system_instruction = f"You are {username}'s personal assistant. You only know facts about them.\n"
        if user_facts:
            system_instruction += "Here is your memory bank regarding this user:\n"
            for fact in user_facts:
                system_instruction += f"- {fact[0]}\n"

        cl.user_session.set("history", [
            {"role": "user", "parts": [system_instruction]},
            {"role": "model", "parts": [f"Ready to assist {username}."]}
        ])
        await cl.Message(content=f"Welcome back, **{username}**. Orion is online and locked to your profile.").send()


@cl.on_message
async def main(message: cl.Message):
    history = cl.user_session.get("history")
    username = cl.user_session.get("username")

    # Build the prompt parts: text + any attached audio files
    current_prompt = [message.content]
    if message.elements:
        for element in message.elements:
            if "audio" in element.mime:
                with open(element.path, "rb") as f:
                    audio_data = f.read()
                current_prompt.append({
                    "mime_type": element.mime,
                    "data": audio_data
                })

    history.append({"role": "user", "parts": current_prompt})

    # Run fact extraction and response generation in parallel
    response, _ = await asyncio.gather(
        asyncio.to_thread(model.generate_content, history),
        extract_and_save_fact(username, message.content),
    )

    history.append({"role": "model", "parts": [response.text]})
    cl.user_session.set("history", history)

    await cl.Message(content=response.text).send()
