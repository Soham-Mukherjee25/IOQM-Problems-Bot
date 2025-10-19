import os
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Your bot's secrets from the Replit "Secrets" tab ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
# This will now securely get the admin ID you just added
ADMIN_ID = int(os.environ['ADMIN_ID']) 

# --- The name of the file where we will store user IDs ---
USER_FILE = "users.txt"


# --- MODIFIED: The start function now saves new user IDs ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and saves the user's ID if they are new."""
    user_id = update.message.from_user.id

    # This block of code checks if the user is new and saves their ID to a file
    try:
        with open(USER_FILE, "r") as f:
            # Create a set of user IDs that we already know
            known_users = {int(line.strip()) for line in f}

        if user_id not in known_users:
            with open(USER_FILE, "a") as f:
                f.write(f"{user_id}\n")
                print(f"New user saved: {user_id}") # Optional: for checking the console
    except FileNotFoundError:
        # If the file doesn't exist, this must be the first user.
        # So, we create the file and add their ID.
        with open(USER_FILE, "w") as f:
            f.write(f"{user_id}\n")
            print(f"User file created. First user saved: {user_id}")

    # The original welcome message
    welcome_message = (
        "Welcome to the IOQM Problems Bot! \n\n"
        "I'm here to help you prepare for the Indian Olympiad Qualifier in Mathematics. "
        "Use the /new_problem command to get a random question from previous years."
    )
    await update.message.reply_text(welcome_message)


# --- NEW: A private command for you to get the user count ---
async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the total number of unique users to the admin."""
    # First, check if the person who sent the command is you (the admin)
    if update.message.from_user.id == ADMIN_ID:
        try:
            with open(USER_FILE, "r") as f:
                user_total = len(f.readlines())
            await update.message.reply_text(f"Total unique users: {user_total}")
        except FileNotFoundError:
            await update.message.reply_text("The user file doesn't exist yet. No users recorded.")
    else:
        # If it's not you, they get this message
        await update.message.reply_text("You do not have permission to use this command.")


# --- This function is your original, unchanged code ---
async def new_problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a random IOQM question picture."""
    try:
        question_files = os.listdir('question')
        if not question_files:
            await update.message.reply_text("Sorry, I can't find any questions right now. Please check back later.")
            return

        random_question_file = random.choice(question_files)
        file_path = os.path.join('question', random_question_file)
        await update.message.reply_photo(photo=open(file_path, 'rb'), caption="Here is your IOQM problem. Good luck!")

    except FileNotFoundError:
        await update.message.reply_text("The 'question' folder was not found. Please make sure it exists and contains question images.")
    except Exception as e:
        print(f"An error occurred: {e}")
        await update.message.reply_text("An error occurred while fetching a new problem.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new_problem", new_problem))
    application.add_handler(CommandHandler("users", user_count)) # <-- NEW: Add the handler for our new command

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()
