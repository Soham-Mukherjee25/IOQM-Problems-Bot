import os
import random
import asyncio
import re
import time
from dataclasses import dataclass
from typing import Iterable
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

app = Flask(__name__)

# --- Secrets ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']

# Global bot application
ptb_app = None
QUESTIONS_CACHE = {"timestamp": 0.0, "items": []}

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


@dataclass(frozen=True)
class QuestionEntry:
    file_path: str
    year: str | None
    subject: str | None

async def initialize_bot():
    """Initializes the bot application."""
    global ptb_app
    ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("new_problem", new_problem))
    ptb_app.add_handler(CallbackQueryHandler(handle_problem_selection, pattern=r"^problem:"))
    
    await ptb_app.initialize()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the welcome message."""
    welcome_message = (
        "Welcome to the IOQM Problems Bot! \n\n"
        "I'm here to help you prepare for the Indian Olympiad Qualifier in Mathematics. \n"
        "Use /new_problem to pick a random question, a subject, a year, or both."
    )
    await update.message.reply_text(welcome_message)

async def new_problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the IOQM question picker."""
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎲 Random (any)", callback_data="problem:any")],
            [
                InlineKeyboardButton("📚 By subject", callback_data="problem:choose_subject"),
                InlineKeyboardButton("📆 By year", callback_data="problem:choose_year"),
            ],
            [
                InlineKeyboardButton(
                    "📚 + 📆 Year & subject", callback_data="problem:choose_year_subject"
                )
            ],
        ]
    )
    await update.message.reply_text(
        "How would you like to pick a question?", reply_markup=keyboard
    )


def _normalize_subject(text: str) -> str | None:
    cleaned = re.sub(r"[_\-\s]+", " ", text.strip().lower())
    return SUBJECT_SYNONYMS.get(cleaned)


def _extract_metadata(
    path_parts: Iterable[str], filename: str | None = None
) -> tuple[str | None, str | None]:
    year = None
    subject = None
    for part in path_parts:
        if YEAR_PATTERN.match(part):
            year = part
            continue
        normalized = _normalize_subject(part)
        if normalized:
            subject = normalized
    if filename:
        filename_year, filename_subject = _extract_from_filename(filename)
        year = year or filename_year
        subject = subject or filename_subject
    return year, subject


def _extract_from_filename(filename: str) -> tuple[str | None, str | None]:
    stem = os.path.splitext(filename)[0].lower()
    tokens = re.split(r"[^a-z0-9]+", stem)
    year = next((token for token in tokens if YEAR_PATTERN.match(token)), None)
    subject = None
    for token in tokens:
        normalized = _normalize_subject(token)
        if normalized:
            subject = normalized
            break
    return year, subject


def _question_root() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "question")


def _load_questions() -> list[QuestionEntry]:
    now = time.time()
    if QUESTIONS_CACHE["items"] and now - QUESTIONS_CACHE["timestamp"] < 60:
        return QUESTIONS_CACHE["items"]

    question_dir = _question_root()
    entries: list[QuestionEntry] = []
    for root, _, files in os.walk(question_dir):
        for filename in files:
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            full_path = os.path.join(root, filename)
            relative = os.path.relpath(full_path, question_dir)
            parts = relative.split(os.sep)[:-1]
            year, subject = _extract_metadata(parts, filename=filename)
            entries.append(QuestionEntry(full_path, year, subject))

    QUESTIONS_CACHE["items"] = entries
    QUESTIONS_CACHE["timestamp"] = now
    return entries


def _unique_years(entries: list[QuestionEntry]) -> list[str]:
    years = sorted({entry.year for entry in entries if entry.year})
    return years


def _unique_subjects(entries: list[QuestionEntry]) -> list[str]:
    subjects = sorted({entry.subject for entry in entries if entry.subject})
    return subjects


def _keyboard_from_items(items: list[str], prefix: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for item in items:
        row.append(InlineKeyboardButton(item, callback_data=f"problem:{prefix}:{item}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="problem:back")])
    return InlineKeyboardMarkup(rows)


async def handle_problem_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    entries = _load_questions()

    if not entries:
        await query.edit_message_text("Sorry, I can't find any questions.")
        return

    if data == "problem:any":
        await _send_random_question(query, entries)
        return

    if data == "problem:choose_subject":
        subjects = _unique_subjects(entries)
        if not subjects:
            await query.edit_message_text(
                "I couldn't detect any subjects. Please organize questions by subject folders."
            )
            return
        await query.edit_message_text(
            "Choose a subject:",
            reply_markup=_keyboard_from_items(subjects, "subject"),
        )
        return

    if data == "problem:choose_year":
        years = _unique_years(entries)
        if not years:
            await query.edit_message_text(
                "I couldn't detect any years. Please organize questions by year folders."
            )
            return
        await query.edit_message_text(
            "Choose a year:",
            reply_markup=_keyboard_from_items(years, "year"),
        )
        return

    if data == "problem:choose_year_subject":
        years = _unique_years(entries)
        if not years:
            await query.edit_message_text(
                "I couldn't detect any years. Please organize questions by year folders."
            )
            return
        context.user_data["pending_year"] = None
        await query.edit_message_text(
            "Pick a year first:",
            reply_markup=_keyboard_from_items(years, "year_for_subject"),
        )
        return

    if data == "problem:back":
        await query.edit_message_text(
            "How would you like to pick a question?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🎲 Random (any)", callback_data="problem:any")],
                    [
                        InlineKeyboardButton(
                            "📚 By subject", callback_data="problem:choose_subject"
                        ),
                        InlineKeyboardButton("📆 By year", callback_data="problem:choose_year"),
                    ],
                    [
                        InlineKeyboardButton(
                            "📚 + 📆 Year & subject",
                            callback_data="problem:choose_year_subject",
                        )
                    ],
                ]
            ),
        )
        return

    if data.startswith("problem:year_for_subject:"):
        selected_year = data.split(":", 2)[2]
        context.user_data["pending_year"] = selected_year
        subjects = sorted(
            {
                entry.subject
                for entry in entries
                if entry.subject and entry.year == selected_year
            }
        )
        if not subjects:
            await query.edit_message_text(
                "I couldn't find subjects for that year. Please organize questions by year/subject."
            )
            return
        await query.edit_message_text(
            f"Year {selected_year} selected. Now choose a subject:",
            reply_markup=_keyboard_from_items(subjects, "year_subject"),
        )
        return

    if data.startswith("problem:subject:"):
        selected_subject = data.split(":", 2)[2]
        filtered = [entry for entry in entries if entry.subject == selected_subject]
        await _send_random_question(
            query, filtered, label=f"{selected_subject} problem"
        )
        return

    if data.startswith("problem:year:"):
        selected_year = data.split(":", 2)[2]
        filtered = [entry for entry in entries if entry.year == selected_year]
        await _send_random_question(query, filtered, label=f"{selected_year} problem")
        return

    if data.startswith("problem:year_subject:"):
        selected_subject = data.split(":", 2)[2]
        selected_year = context.user_data.get("pending_year")
        if not selected_year:
            years = _unique_years(entries)
            if not years:
                await query.edit_message_text(
                    "Please select a year first, but I couldn't detect any years."
                )
                return
            await query.edit_message_text(
                "Please select a year first:",
                reply_markup=_keyboard_from_items(years, "year_for_subject"),
            )
            return
        filtered = [
            entry
            for entry in entries
            if entry.year == selected_year and entry.subject == selected_subject
        ]
        await _send_random_question(
            query,
            filtered,
            label=f"{selected_year} {selected_subject} problem",
        )


async def _send_random_question(
    query, entries: list[QuestionEntry], label: str = "IOQM problem"
) -> None:
    if not entries:
        await query.edit_message_text(
            "Sorry, I can't find any questions for that selection."
        )
        return
    entry = random.choice(entries)
    try:
        with open(entry.file_path, "rb") as photo_file:
            await query.message.reply_photo(
                photo=photo_file,
                caption=f"Here is your {label}. Good luck!",
                read_timeout=60,
                write_timeout=60,
                connect_timeout=60,
            )
    except Exception as e:
        print(f"Error: {e}")
        return

@app.route('/', methods=['POST'])
def webhook_handler():
    """Handles incoming Telegram updates."""
    if request.method == "POST":
        try:
            asyncio.run(process_update())
        except Exception as e:
            print(f"Webhook Error: {e}")
        return "OK"
    return "Bot is running!"

async def process_update():
    global ptb_app
    if ptb_app is None:
        await initialize_bot()
        
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    await ptb_app.process_update(update)
