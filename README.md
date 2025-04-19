# Telegram Study Words Bot

A Telegram bot that helps users learn words and phrases through interactive quizzes. The bot supports multiple quiz modes and allows users to manage their own vocabulary lists.

## Features

- 🔀 Create quizzes with mixed answers
- 🔄 Create quizzes with mixed phrases
- 🎲 Create random quizzes from your vocabulary
- 📋 List and manage your phrases
- 🤖 Interactive quiz creation through conversation handlers

## Commands

- `/start` - Get started with the bot and see available commands
- `/list` - View your saved phrases
- `/create_quiz_mix_answers` - Create a quiz with mixed answers
- `/create_quiz_mix_phrases` - Create a quiz with mixed phrases
- `/create_random_quiz` - Create a random quiz from your phrases
- `/help` - Get help and see available commands
- `/cancel` - Cancel the current operation

## Setup

1. Clone the repository
2. Install dependencies from requirements.txt:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the following variables:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TARGET_CHAT_ID=your_chat_id
   ```
4. Run the bot:
   ```bash
   python main.py
   ```

## Usage

1. Start the bot with `/start` command
2. Add phrases using one of the quiz creation commands
3. Format your phrases as: `phrase - translation`
4. The bot will create interactive quizzes in the target chat
5. Use `/list` to view your saved phrases

## Quiz Modes

### Mixed Answers Quiz

- Question shows a phrase
- Answers include the correct translation and other translations from your vocabulary
- Helps learn correct translations among similar options

### Mixed Phrases Quiz

- Question shows a translation
- Answers include the correct phrase and other phrases from your vocabulary
- Helps learn phrases from their translations

### Random Quiz

- Choose between translation or phrase mode
- Select random or specific phrases
- Get a customized quiz based on your preferences

## Requirements

- Python 3.7+
- python-telegram-bot==20.7
- python-dotenv==1.0.0
- google-generativeai==0.8.4
- langchain==0.3.18
- langchain-google-genai==2.0.7
- langchain-core==0.3.34
- pydantic==2.9.2
