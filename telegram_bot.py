import json
import time
import os
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# --- SECURE CREDENTIALS ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AIPIPE_TOKEN = os.environ.get("AIPIPE_TOKEN")
LOG_URL = os.environ.get("LOG_URL")

if AIPIPE_TOKEN:
    client = OpenAI(base_url="https://aipipe.org/openai/v1", api_key=AIPIPE_TOKEN)

LOG_FILE = "run.jsonl"
conversation_history = {}

def log_event(event: dict):
    event["timestamp"] = time.time()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text
    log_event({"type": "incoming", "chat_id": chat_id, "text": user_text})

    history = conversation_history.setdefault(chat_id, [])
    history.append({"role": "user", "content": user_text})

    system_prompt = (
        "You are a careful data analyst. The user's LAST message asks a data-analysis "
        "question and tells you exactly what JSON shape to reply with. Work out the "
        "real answer (use any public data you know, e.g. MOSPI statistics, general "
        "world knowledge, or arithmetic on numbers given in the message). "
        "Reply with ONLY that exact JSON object and absolutely nothing else — no "
        "explanation, no markdown, no code fences, just the raw JSON."
    )
    
    response = client.chat.completions.create(
        model="gpt-5-mini", # Make sure this matches the model you want to use
        messages=[{"role": "system", "content": system_prompt}] + history[-6:],
    )
    reply_text = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply_text})

    try:
        parsed = json.loads(reply_text)
    except json.JSONDecodeError:
        start, end = reply_text.find("{"), reply_text.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(reply_text[start:end + 1])
        else:
            parsed = {}
            
    parsed["log_url"] = LOG_URL
    final_reply = json.dumps(parsed)

    log_event({"type": "outgoing", "chat_id": chat_id, "text": final_reply})
    await update.message.reply_text(final_reply)

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN or not AIPIPE_TOKEN or not LOG_URL:
        print("ERROR: Missing Environment Variables.")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("Bot is running on Railway... (Ctrl+C to stop)")
        app.run_polling()
