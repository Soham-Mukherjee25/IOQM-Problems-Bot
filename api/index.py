import os
import random
import asyncio
from dataclasses import dataclass
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Global bot application
ptb_app = None

@dataclass(frozen=True)
class QuestionEntry:
    file_path: str

def _load_questions():
    """Scans the 'question' directory for image files."""
    entries = []
    
    # 1. Calculate the path to the 'question' folder relative to this script
    # This script is in /api, so we go up one level (..) to find /question
    base_dir = os.path.dirname(os.path.abspath(__file__)) # The 'api' folder
    root_dir = os.path.dirname(base_dir)                  # The root folder
    questions_path = os.path.join(root_dir, 'question')

    # Debug print (you can see this in Vercel logs)
    print(f"Looking for questions in: {questions_path}")
    
    # Check if folder exists
    if not os.path.exists(questions_path):
        # Fallback: Try looking in current directory just in case structure changed
        if os.path.exists("question"):
            questions_path = "question"
        else:
            print(f"Error: Folder '{questions_path}' not found.")
            return []

    # Walk through directory
    for root, _, files in os.walk(questions_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                full_path = os.path.join(root, file)
                entries.append(QuestionEntry(file_path=full_path))
    
    print(f"Found {len(entries)} questions.")
    return entries

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the IOQM Problems Bot!\n"
        "Use /new_problem to get a random question."
    )

async def new_problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    entries = _load_questions()
    
    if not entries:
        await update.message.reply_text("Sorry, I can't find any questions. (Check Vercel Logs)")
        return

    entry = random.choice(entries)
    
    # Send "uploading photo..." action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")

    try:
        with open(entry.file_path, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption="Here is your IOQM problem. Good luck!"
            )
    except Exception as e:
        print(f"Error sending file {entry.file_path}: {e}")
        await update.message.reply_text("Error uploading the image.")

# --- Initialization & Webhook ---
async def initialize_bot():
    global ptb_app
    if ptb_app is None:
        ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
        ptb_app.add_handler(CommandHandler("start", start))
        ptb_app.add_handler(CommandHandler("new_problem", new_problem))
        await ptb_app.initialize()

@app.route('/', methods=['POST'])
async def webhook_handler():
    global ptb_app
    await initialize_bot()
    
    if request.method == "POST":
        try:
            data = request.get_json(force=True)
            update = Update.de_json(data, ptb_app.bot)
            await ptb_app.process_update(update)
            return "OK"
        except Exception as e:
            print(f"Webhook error: {e}")
            return "Error", 500
    return "Bot is running"

@app.route('/', methods=['GET'])
def index():
    return "Bot is running! ensure webhook is set."
