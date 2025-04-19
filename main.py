# flake8: noqa: E501

import logging
import os
from dotenv import load_dotenv
import random
from typing import Dict
import asyncio

from telegram import (
    KeyboardButton,
    KeyboardButtonPollType,
    Poll,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PollAnswerHandler,
    PollHandler,
    filters,
    ConversationHandler,
)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID"))

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Conversation states
WAITING_FOR_PHRASE = 0
WAITING_FOR_MIX_PHRASE = 1
WAITING_FOR_MIX_PHRASES_REVERSED = 2
SELECTING_QUIZ_MODE = 3
SELECTING_PHRASES = 4

# Dictionary to store user phrases
user_phrases: Dict[int, Dict[str, str]] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inform user about what this bot can do"""
    await update.message.reply_text(
        "Welcome to the Translation Quiz Bot! 🎯\n\n"
        "📋 /list – See your phrases\n"
        "ℹ️ /help – More information\n"
        "🔀 /create_quiz_mix_answers – Create quizzes with mixed answers\n"
        "🔄 /create_quiz_mix_phrases – Create quizzes with mixed phrases\n"
        "🎲 /create_random_quiz – Create random quiz from your phrases\n"
        "❌ /cancel – Cancel the current operation\n\n"
    )


async def add_quiz_mix(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the process of adding new mixed quizzes"""
    await update.message.reply_text(
        "📝 Please send me phrases and translations in the format:\n"
        "`phrase - translation`\n\n"
        "📄 You can send multiple phrases at once, one per line.\n"
        "🤓 I will create quizzes where incorrect options are correct translations of other phrases!\n\n"
        "📌 Example:\n"
        "`buzzkill - душніла, зануда`\n"
        "`no rush - не спіши`",
        parse_mode="Markdown",
    )
    return WAITING_FOR_MIX_PHRASE


async def add_quiz_mix_phrases(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the process of adding new mixed quizzes with reversed format"""
    await update.message.reply_text(
        "🔁 Please send me phrases and translations in the format:\n"
        "`phrase - translation`\n\n"
        "📄 You can send multiple phrases at once, one per line.\n"
        "🎯 I will create quizzes where the *translation* is the question and the *phrase* is the answer!\n\n"
        "📌 Example:\n"
        "`hello - привіт`\n"
        "`goodbye - до побачення`",
        parse_mode="Markdown",
    )
    return WAITING_FOR_MIX_PHRASES_REVERSED


def truncate_translation(translation: str, max_length: int = 95) -> str:
    """Truncate translation to fit within Telegram's poll option limit"""
    if len(translation) > max_length:
        return translation[:max_length] + "..."
    return translation


async def receive_mix_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parse phrases and create mixed quizzes where wrong answers are other correct translations"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Initialize user's phrase dictionary if it doesn't exist
    if user_id not in user_phrases:
        user_phrases[user_id] = {}

    # Split input into lines and process each line
    lines = text.split("\n")
    phrases_and_translations = []
    added_count = 0
    error_count = 0
    quiz_messages = []

    # First, collect all valid phrases and translations
    for line in lines:
        line = line.strip()
        if not line:
            continue

        line = line.replace("✅", "").strip()
        parts = line.split(" - ", 1)
        if len(parts) != 2:
            error_count += 1
            continue

        phrase, translation = parts
        phrase = phrase.strip()
        translation = translation.strip()

        if translation.endswith("."):
            translation = translation[:-1]

        user_phrases[user_id][phrase] = translation
        phrases_and_translations.append((phrase, translation))
        added_count += 1

    # Now create quizzes using other translations as wrong answers
    for phrase, correct_translation in phrases_and_translations:
        # Get other translations as wrong options
        other_translations = [
            t for p, t in phrases_and_translations if t != correct_translation
        ]

        # If we don't have enough other translations, skip this phrase
        if len(other_translations) < 3:
            continue

        # Select 3 random translations as wrong options
        wrong_options = random.sample(
            other_translations, min(3, len(other_translations))
        )

        # Truncate all options to fit within Telegram's limit
        truncated_translation = truncate_translation(correct_translation)
        truncated_incorrect = [truncate_translation(opt) for opt in wrong_options]

        # Combine all options and shuffle them
        all_options = [truncated_translation] + truncated_incorrect
        random.shuffle(all_options)

        # Find the index of the correct answer
        correct_index = all_options.index(truncated_translation)

        # Create quiz for this phrase in the target chat
        message = await context.bot.send_poll(
            chat_id=TARGET_CHAT_ID,
            question=f"📝 Який правильний переклад «{phrase}»?",
            options=all_options,
            type=Poll.QUIZ,
            correct_option_id=correct_index,
        )

        # Add 2-second delay between polls
        await asyncio.sleep(2)

        # Save quiz info for later use
        payload = {
            message.poll.id: {
                "chat_id": TARGET_CHAT_ID,
                "message_id": message.message_id,
            }
        }
        context.bot_data.update(payload)
        quiz_messages.append(message)

    # Send feedback to user
    if added_count > 0:
        message = f"✅ Successfully added {added_count} phrase(s)!\n"
        if error_count > 0:
            message += f"❌ {error_count} line(s) couldn't be processed.\n"
        message += f"\nCreated {len(quiz_messages)} mixed quiz(es) in the target chat!"
    else:
        message = "❌ No phrases were added. Please make sure to use the format:\nphrase - translation"

    await update.message.reply_text(message)
    return ConversationHandler.END


async def receive_mix_phrases_reversed(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Parse phrases and create mixed quizzes where translation is the question and phrase is the answer"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Initialize user's phrase dictionary if it doesn't exist
    if user_id not in user_phrases:
        user_phrases[user_id] = {}

    # Split input into lines and process each line
    lines = text.split("\n")
    phrases_and_translations = []
    added_count = 0
    error_count = 0
    quiz_messages = []

    # First, collect all valid phrases and translations
    for line in lines:
        line = line.strip()
        if not line:
            continue

        line = line.replace("✅", "").strip()
        parts = line.split(" - ", 1)
        if len(parts) != 2:
            error_count += 1
            continue

        phrase, translation = parts
        phrase = phrase.strip()
        translation = translation.strip()

        if translation.endswith("."):
            translation = translation[:-1]

        user_phrases[user_id][phrase] = translation
        phrases_and_translations.append((phrase, translation))
        added_count += 1

    # Now create quizzes using other phrases as wrong answers
    for phrase, translation in phrases_and_translations:
        # Get other phrases as wrong options
        other_phrases = [p for p, t in phrases_and_translations if p != phrase]

        # If we don't have enough other phrases, skip this translation
        if len(other_phrases) < 3:
            continue

        # Select 3 random phrases as wrong options
        wrong_options = random.sample(other_phrases, min(3, len(other_phrases)))

        # Truncate all options to fit within Telegram's limit
        truncated_phrase = truncate_translation(phrase)
        truncated_incorrect = [truncate_translation(opt) for opt in wrong_options]

        # Combine all options and shuffle them
        all_options = [truncated_phrase] + truncated_incorrect
        random.shuffle(all_options)

        # Find the index of the correct answer
        correct_index = all_options.index(truncated_phrase)

        # Create quiz for this translation in the target chat
        message = await context.bot.send_poll(
            chat_id=TARGET_CHAT_ID,
            question=f"📝 What is the English phrase for «{translation}»?",
            options=all_options,
            type=Poll.QUIZ,
            correct_option_id=correct_index,
        )

        # Add 2-second delay between polls
        await asyncio.sleep(2)

        # Save quiz info for later use
        payload = {
            message.poll.id: {
                "chat_id": TARGET_CHAT_ID,
                "message_id": message.message_id,
            }
        }
        context.bot_data.update(payload)
        quiz_messages.append(message)

    # Send feedback to user
    if added_count > 0:
        message = f"✅ Successfully added {added_count} phrase(s)!\n"
        if error_count > 0:
            message += f"❌ {error_count} line(s) couldn't be processed.\n"
        message += f"\nCreated {len(quiz_messages)} mixed quiz(es) in the target chat!"
    else:
        message = "❌ No phrases were added. Please make sure to use the format:\nphrase - translation"

    await update.message.reply_text(message)
    return ConversationHandler.END


async def list_phrases(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all phrases added by the user"""
    user_id = update.effective_user.id
    if user_id not in user_phrases or not user_phrases[user_id]:
        await update.message.reply_text(
            "You haven't added any phrases yet. Use /add to add some!"
        )
        return

    message = "📚 Your phrases:\n\n"
    for phrase, translation in user_phrases[user_id].items():
        message += f"✅ {phrase} - {translation}\n"

    await update.message.reply_text(message)


TOTAL_VOTER_COUNT = 3


async def receive_poll_answer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Summarize a users poll vote"""
    answer = update.poll_answer
    answered_poll = context.bot_data[answer.poll_id]
    try:
        questions = answered_poll["questions"]
    # this means this poll answer update is from an old poll, we can't do our answering then
    except KeyError:
        return
    selected_options = answer.option_ids
    answer_string = ""
    for question_id in selected_options:
        if question_id != selected_options[-1]:
            answer_string += questions[question_id] + " and "
        else:
            answer_string += questions[question_id]
    await context.bot.send_message(
        answered_poll["chat_id"],
        f"{update.effective_user.mention_html()} feels {answer_string}!",
        parse_mode=ParseMode.HTML,
    )
    answered_poll["answers"] += 1
    # Close poll after three participants voted
    if answered_poll["answers"] == TOTAL_VOTER_COUNT:
        await context.bot.stop_poll(
            answered_poll["chat_id"], answered_poll["message_id"]
        )


async def receive_quiz_answer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Close quiz after three participants took it"""
    # the bot can receive closed poll updates we don't care about
    if update.poll.is_closed:
        return
    if update.poll.total_voter_count == TOTAL_VOTER_COUNT:
        try:
            quiz_data = context.bot_data[update.poll.id]
        # this means this poll answer update is from an old poll, we can't stop it then
        except KeyError:
            return
        await context.bot.stop_poll(quiz_data["chat_id"], quiz_data["message_id"])


async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask user to create a poll and display a preview of it"""
    # using this without a type lets the user chooses what he wants (quiz or poll)
    button = [[KeyboardButton("Press me!", request_poll=KeyboardButtonPollType())]]
    message = "Press the button to let the bot generate a preview for your poll"
    # using one_time_keyboard to hide the keyboard
    await update.effective_message.reply_text(
        message, reply_markup=ReplyKeyboardMarkup(button, one_time_keyboard=True)
    )


async def receive_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On receiving polls, reply to it by a closed poll copying the received poll"""
    actual_poll = update.effective_message.poll
    # Only need to set the question and options, since all other parameters don't matter for
    # a closed poll
    await update.effective_message.reply_poll(
        question=actual_poll.question,
        options=[o.text for o in actual_poll.options],
        # with is_closed true, the poll/quiz is immediately closed
        is_closed=True,
        reply_markup=ReplyKeyboardRemove(),
    )


async def create_random_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the process of creating a random quiz"""
    user_id = update.effective_user.id
    if user_id not in user_phrases or not user_phrases[user_id]:
        await update.message.reply_text(
            "❌ You haven't added any phrases yet. Use /create_quiz_mix_answers or /create_quiz_mix_phrases to add some!"
        )
        return ConversationHandler.END

    # Create keyboard with quiz modes
    keyboard = [
        [
            KeyboardButton("🔀 Translation Quiz"),
            KeyboardButton("🔄 Phrase Quiz"),
        ],
        [KeyboardButton("❌ Cancel")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "🎲 Choose quiz mode:\n\n"
        "🔀 Translation Quiz - Question is phrase, answers are translations\n"
        "🔄 Phrase Quiz - Question is translation, answers are phrases",
        reply_markup=reply_markup,
    )
    return SELECTING_QUIZ_MODE


async def select_quiz_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quiz mode selection and ask for phrase selection"""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "❌ Cancel":
        await update.message.reply_text(
            "Operation cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    # Store selected mode in context
    if text == "🔀 Translation Quiz":
        context.user_data["quiz_mode"] = "translation"
    elif text == "🔄 Phrase Quiz":
        context.user_data["quiz_mode"] = "phrase"
    else:
        await update.message.reply_text("Please select a valid mode.")
        return SELECTING_QUIZ_MODE

    # Create keyboard with phrase selection options
    keyboard = [
        [KeyboardButton("🎲 Random")],
        [KeyboardButton("📋 All")],
        [KeyboardButton("❌ Cancel")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    # Show user's phrases
    phrases = list(user_phrases[user_id].items())
    message = "📚 Your phrases:\n\n"
    for i, (phrase, translation) in enumerate(phrases, 1):
        message += f"{i}. {phrase} - {translation}\n"

    message += "\n🎯 Choose phrases:\n"
    message += "🎲 Random - Get random phrase\n"
    message += "📋 All - Use all phrases\n"
    message += "❌ Cancel - Cancel operation"

    await update.message.reply_text(message, reply_markup=reply_markup)
    return SELECTING_PHRASES


async def create_quiz_from_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Create quiz based on selected mode and phrases"""
    user_id = update.effective_user.id
    text = update.message.text
    quiz_mode = context.user_data.get("quiz_mode")

    if text == "❌ Cancel":
        await update.message.reply_text(
            "Operation cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    # Get phrases to use
    phrases = list(user_phrases[user_id].items())
    if not phrases:
        await update.message.reply_text(
            "No phrases available.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    if text == "🎲 Random":
        selected_phrases = [random.choice(phrases)]
    elif text == "📋 All":
        selected_phrases = phrases
    else:
        try:
            index = int(text) - 1
            if 0 <= index < len(phrases):
                selected_phrases = [phrases[index]]
            else:
                await update.message.reply_text(
                    "Invalid phrase number.", reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        except ValueError:
            await update.message.reply_text(
                "Please select a valid option.", reply_markup=ReplyKeyboardRemove()
            )
            return SELECTING_PHRASES

    quiz_messages = []
    for phrase, translation in selected_phrases:
        if quiz_mode == "translation":
            # Get other translations as wrong options
            other_translations = [t for p, t in phrases if t != translation]
            if len(other_translations) < 3:
                continue

            wrong_options = random.sample(
                other_translations, min(3, len(other_translations))
            )
            truncated_translation = truncate_translation(translation)
            truncated_incorrect = [truncate_translation(opt) for opt in wrong_options]
            all_options = [truncated_translation] + truncated_incorrect
            random.shuffle(all_options)
            correct_index = all_options.index(truncated_translation)

            message = await context.bot.send_poll(
                chat_id=TARGET_CHAT_ID,
                question=f"📝 Який правильний переклад «{phrase}»?",
                options=all_options,
                type=Poll.QUIZ,
                correct_option_id=correct_index,
            )
        else:  # phrase mode
            # Get other phrases as wrong options
            other_phrases = [p for p, t in phrases if p != phrase]
            if len(other_phrases) < 3:
                continue

            wrong_options = random.sample(other_phrases, min(3, len(other_phrases)))
            truncated_phrase = truncate_translation(phrase)
            truncated_incorrect = [truncate_translation(opt) for opt in wrong_options]
            all_options = [truncated_phrase] + truncated_incorrect
            random.shuffle(all_options)
            correct_index = all_options.index(truncated_phrase)

            message = await context.bot.send_poll(
                chat_id=TARGET_CHAT_ID,
                question=f"📝 What is the English phrase for «{translation}»?",
                options=all_options,
                type=Poll.QUIZ,
                correct_option_id=correct_index,
            )

        await asyncio.sleep(2)
        payload = {
            message.poll.id: {
                "chat_id": TARGET_CHAT_ID,
                "message_id": message.message_id,
            }
        }
        context.bot_data.update(payload)
        quiz_messages.append(message)

    await update.message.reply_text(
        f"✅ Created {len(quiz_messages)} quiz(es) in the target chat!",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display a help message"""
    await update.message.reply_text(
        "🆘 Help Menu\n\n"
        "▶️ Use /start to see the available commands.\n\n"
        "🔀 /create_quiz_mix_answers – Create quizzes with mixed answers\n"
        "🔄 /create_quiz_mix_phrases – Create quizzes with mixed phrases\n"
        "🎲 /create_random_quiz – Create random quiz from your phrases\n"
        "📋 /list – List your phrases\n",
    )


def main() -> None:
    """Run bot."""
    # Create the Application and pass it your bot's token.
    print("Starting bot...")
    token = TELEGRAM_BOT_TOKEN
    application = Application.builder().token(token).build()

    # Add conversation handler for adding phrases
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("create_quiz_mix_answers", add_quiz_mix),
            CommandHandler("create_quiz_mix_phrases", add_quiz_mix_phrases),
            CommandHandler("create_random_quiz", create_random_quiz),
        ],
        states={
            WAITING_FOR_MIX_PHRASE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_mix_phrase)
            ],
            WAITING_FOR_MIX_PHRASES_REVERSED: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_mix_phrases_reversed
                )
            ],
            SELECTING_QUIZ_MODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_quiz_mode)
            ],
            SELECTING_PHRASES: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, create_quiz_from_selection
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_phrases))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(PollAnswerHandler(receive_quiz_answer))
    application.add_handler(PollHandler(receive_quiz_answer))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
