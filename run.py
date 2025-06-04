#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import asyncio
import html
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# Импорт классов и функций из aiogram v3.x
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.enums import ParseMode

# Импорт клиента OpenAI (beta-эндпоинты)
from openai import OpenAI

import nest_asyncio
nest_asyncio.apply()

# -----------------------------------------------------------------------------
#                       ЧТЕНИЕ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# -----------------------------------------------------------------------------
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_3M2ZQIU1n6kiRzLFrdKpCVTW")  # можно задавать в .env

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Не найден TELEGRAM_BOT_TOKEN в переменных окружения (.env).")
if not OPENAI_API_KEY:
    raise ValueError("Не найден OPENAI_API_KEY в переменных окружения (.env).")

# -----------------------------------------------------------------------------
#                           НАСТРОЙКА ЛОГИРОВАНИЯ
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
#                       ИНИЦИАЛИЗАЦИЯ КЛИЕНТА OpenAI
# -----------------------------------------------------------------------------
client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------------------------------------------------------
#                   ИНИЦИАЛИЗАЦИЯ TELEGRAM-БОТА (aiogram v3.x)
# -----------------------------------------------------------------------------
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()  # Создаём роутер для регистрации обработчиков
dp.include_router(router)

# Словарь для хранения связки user_id -> thread_id.
user_threads: Dict[int, str] = {}

# Глобальная переменная для хранения главного event loop.
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None

# -----------------------------------------------------------------------------
#                        КЛАСС ДЛЯ РАБОТЫ С OpenAI (Beta)
# -----------------------------------------------------------------------------

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class OpenAIClientAsync:
    """
    Асинхронный клиент для работы с OpenAI Assistant API (beta).
    """
    def __init__(self, api_key: str, assistant_id: str, logger: logging.Logger):
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        self.logger = logger

    async def create_thread(self) -> Optional[str]:
        try:
            thread_obj = await asyncio.to_thread(self.client.beta.threads.create)
            self.logger.info(f"Создан новый thread с id: {thread_obj.id}")
            return thread_obj.id
        except Exception as e:
            self.logger.exception("Ошибка при создании thread.")
            return None

    async def send_message(self, thread_id: str, message: str) -> bool:
        try:
            await asyncio.to_thread(
                self.client.beta.threads.messages.create,
                thread_id=thread_id,
                role="user",
                content=message,
            )
            self.logger.info(f"Сообщение пользователя отправлено в thread {thread_id}")
            return True
        except Exception as e:
            self.logger.exception(f"Ошибка при отправке сообщения в thread {thread_id}.")
            return False

    async def run_assistant(self, thread_id: str) -> Optional[str]:
        try:
            run_obj = await asyncio.to_thread(
                self.client.beta.threads.runs.create,
                assistant_id=self.assistant_id,
                thread_id=thread_id,
            )
            self.logger.info(f"Создан run {run_obj.id} для thread {thread_id}")
            return run_obj.id
        except Exception as e:
            self.logger.exception(f"Ошибка при создании run для thread {thread_id}.")
            return None

    async def get_run_steps(self, thread_id: str, run_id: str) -> List[Any]:
        try:
            steps_page = await asyncio.to_thread(
                self.client.beta.threads.runs.steps.list,
                thread_id=thread_id,
                run_id=run_id
            )
            return list(steps_page)
        except Exception as e:
            self.logger.exception(f"Ошибка при получении run steps для run {run_id}.")
            return []

    async def retrieve_message(self, thread_id: str, message_id: str) -> Any:
        try:
            msg_obj = await asyncio.to_thread(
                self.client.beta.threads.messages.retrieve,
                thread_id=thread_id,
                message_id=message_id,
            )
            return msg_obj
        except Exception as e:
            self.logger.exception(f"Ошибка при извлечении сообщения {message_id} из thread {thread_id}.")
            return None

    def extract_text_from_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, list):
            parts = []
            for seg in content:
                if isinstance(seg, dict):
                    text_val = seg.get("text", {}).get("value", "")
                    parts.append(text_val)
                elif hasattr(seg, "text"):
                    try:
                        parts.append(seg.text.value)
                    except Exception:
                        parts.append(str(seg.text))
                else:
                    parts.append(str(seg))
            return "".join(parts)
        if hasattr(content, "text"):
            try:
                return content.text.value
            except Exception:
                return str(content.text)
        return str(content)

    async def poll_run_steps(self, thread_id: str, run_id: str, chat_id: int,
                            bot: Bot,
                            max_attempts: int = 20, interval: int = 2) -> str:
        final_answer: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            try:
                await bot.send_chat_action(chat_id, action="typing")
            except Exception:
                pass
            steps = await self.get_run_steps(thread_id, run_id)
            for step in steps:
                step_details = getattr(step, "step_details", None)
                if step_details and getattr(step_details, "type", "") == "message_creation":
                    msg_creation = step_details.message_creation
                    message_id = getattr(msg_creation, "message_id", None)
                    if message_id:
                        msg_obj = await self.retrieve_message(thread_id, message_id)
                        if msg_obj:
                            content = getattr(msg_obj, "content", None)
                            final_answer = self.extract_text_from_content(content)
                            if final_answer and final_answer.strip():
                                self.logger.info(f"Ответ ассистента получен на попытке {attempt}.")
                                return final_answer
            await asyncio.sleep(interval)
        return final_answer or "❗️ Не удалось получить ответ от ассистента. Попробуйте позже."

    async def process_user_request(self, thread_id: str, user_question: str, chat_id: int, bot: Bot) -> str:
        ok = await self.send_message(thread_id, user_question)
        if not ok:
            return "❗️ Ошибка при отправке сообщения. Попробуйте позже."
        run_id = await self.run_assistant(thread_id)
        if not run_id:
            return "❗️ Ошибка при запуске ассистента. Попробуйте позже."
        final_answer = await self.poll_run_steps(thread_id, run_id, chat_id=chat_id, bot=bot)
        return final_answer

# Инициализация асинхронного клиента
openai_client_async = OpenAIClientAsync(api_key=OPENAI_API_KEY, assistant_id=ASSISTANT_ID, logger=logger)

# Красивая клавиатура для UX
main_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Задать новый вопрос", callback_data="ask_new")],
        [InlineKeyboardButton(text="Начать заново", callback_data="start_over")]
    ]
)

# -----------------------------------------------------------------------------
#                   ОБРАБОТЧИКИ СООБЩЕНИЙ TELEGRAM (aiogram v3.x)
# -----------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start. Создает (или восстанавливает) thread для пользователя.
    """
    user_id = message.from_user.id
    if user_id not in user_threads:
        try:
            thread_obj = await asyncio.to_thread(create_thread_for_user)
            thread_id = getattr(thread_obj, "id", None)
            if not thread_id:
                await message.answer("Ошибка: не получен thread ID.")
                return

            user_threads[user_id] = thread_id
            logger.info(f"Thread {thread_id} создан для пользователя {user_id}")
        except Exception as e:
            logger.exception(f"Ошибка создания thread для пользователя {user_id}.")
            await message.answer(f"Ошибка при создании thread: {e}")
            return
    else:
        thread_id = user_threads[user_id]

    welcome_text = (
        f"Привет, я твой помощник!\n"
        f"Твой thread ID: {thread_id}\n"
        f"Чтобы задать вопрос, используй команду: /ask <твой вопрос>"
    )
    await message.answer(welcome_text)

@router.message(Command("ask"))
async def cmd_ask(message: types.Message):
    """
    Обработчик команды /ask <вопрос>.
    """
    user_id = message.from_user.id
    if user_id not in user_threads:
        await message.answer("Сначала отправьте /start для создания thread.")
        return

    thread_id = user_threads[user_id]
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Пожалуйста, введите вопрос после /ask.")
        return

    user_question = parts[1].strip()
    await message.answer("Подумаем над ответом…")

    try:
        answer = await asyncio.to_thread(process_user_request, thread_id, user_question, message.chat.id)
        await message.answer(f"Ответ ассистента:\n\n{answer}", parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.exception("Ошибка при получении ответа от ассистента.")
        await message.answer(f"Произошла ошибка: {e}", parse_mode=types.ParseMode.HTML)


@router.message(lambda message: message.content_type == "text")
async def handle_text_messages(message: types.Message):
    """
    Обработчик любых текстовых сообщений, которые не являются командами.
    """
    if message.text.startswith("/"):
        await message.answer("Неизвестная команда. Попробуйте /start или /ask.")
    else:
        await message.answer("Вы отправили сообщение без команды. Если хотите задать вопрос ассистенту, используйте /ask <твой вопрос>.")

@router.message(lambda message: message.content_type == "photo")
async def handle_photo_messages(message: types.Message):
    """
    Пример обработки фото: пока бот не умеет обрабатывать изображения.
    """
    await message.answer("Вы прислали фото, но я пока не умею его обрабатывать.")

# -----------------------------------------------------------------------------
#                              ЗАПУСК БОТА (aiogram v3.x)
# -----------------------------------------------------------------------------
async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    logger.info("Запускаем Telegram-бота на aiogram v3.x...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
