# Telegram OpenAI Assistant Bot

This bot integrates the Telegram API with OpenAI Assistants. It requires Python 3.10+.

## Setup
1. Create a copy of `.env.example` named `.env` and fill in your credentials.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   (or install `aiogram`, `openai`, `python-dotenv` manually.)
3. Run the bot:
   ```bash
   python run.py
   ```

## Testing
Run the test suite with:
```bash
pytest
```
