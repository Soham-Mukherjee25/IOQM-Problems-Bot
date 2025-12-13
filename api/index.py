import os
import random
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

# --- Secrets ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']

ptb_app = None

async def initialize_bot():
    global ptb_app
    ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("new_problem", new_problem))
    await ptb_app.initialize()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_message = (
        "Welcome to the IOQM Problems Bot! \n\n"
        "I'm here to help you prepare for the Indian Olympiad Qualifier in Mathematics. "
        "Use the /new_problem command to get a random question."
    )
    await update.message.reply_text(welcome_message)

async def new_problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Look one directory up (..) to find the 'question' folder
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        question_dir = os.path.join(base_dir, 'question')
        
        question_files = os.listdir(question_dir)
        
        if not question_files:
            await update.message.reply_text("Sorry, I can't find any questions.")
            return

        random_question_file = random.choice(question_files)
        file_path = os.path.join(question_dir, random_question_file)
        
        await update.message.reply_photo(
            photo=open(file_path, 'rb'), 
            caption="Here is your IOQM problem. Good luck!"
        )

    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("An error occurred while fetching a problem.")

@app.route('/', methods=['POST'])
def webhook_handler():
    if request.method == "POST":
        asyncio.run(process_update())
        return "OK"
    return "Bot is running!"

async def process_update():
    global ptb_app
    if ptb_app is None:
        await initialize_bot()
    
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    await ptb_app.process_update(update)
