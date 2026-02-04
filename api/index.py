import os
import random
import asyncio
import re
import json
import time
from dataclasses import dataclass
from typing import Iterable
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

app = Flask(__name__)

# --- Secrets ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']

# Global bot application
ptb_app = None
QUESTIONS_CACHE = {
    "timestamp": 0.0,
    "items": [],
    "metadata": {},
}

SUBJECT_SYNONYMS = {
    "algebra": "Algebra",
    "geometry": "Geometry",
    "combinatorics": "Combinatorics",
    "comb": "Combinatorics",
    "numbertheory": "Number Theory",
    "number_theory": "Number Theory",
    "number-theory": "Number Theory",
    "nt": "Number Theory",
    "number theory": "Number Theory",
}

YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")
CACHE_TTL_SECONDS = 600

@dataclass(frozen=True)
class QuestionEntry:
    file_path: str
    year: str | None
    subject: str | None

async def initialize_bot():
    global ptb_app
    ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("new_problem", new_problem))
    
    await ptb_app.initialize()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_message = (
        "Welcome to the IOQM Problems Bot! \n\n"
        "I'm here to help you prepare for the Indian Olympiad Qualifier in Mathematics. \n"
        "Use /new_problem to get a random question immediately."
    )
    await update.message.reply_text(welcome_message)

async def new_problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    entries = _load_questions()
    if not entries:
        await update.message.reply_text("Sorry, I can't find any questions.")
        return

    entry = random.choice(entries)
    try:
        with open(entry.file_path, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption="Here is your IOQM problem. Good luck!",
                read_timeout=60,
                write_timeout=60,
                connect_timeout=60,
            )
    except Exception as e:
        print(f"Error sending random question: {e}")
        await update.message.reply_text("Sorry, I couldn't send the question right now.")

# (rest of the original code continues unchanged)