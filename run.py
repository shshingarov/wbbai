#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from typing import Optional, Dict, Any

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


# -----------------------------------------------------------------------------
#                   ИНИЦИАЛИЗАЦИЯ TELEGRAM-БОТА (aiogram v3.x)
# -----------------------------------------------------------------------------
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()  # Создаём роутер для регистрации обработчиков
dp.include_router(router)

# Словарь для хранения связки user_id -> thread_id.
user_threads: Dict[int, str] = {}

# -----------------------------------------------------------------------------
#                        КЛАСС ДЛЯ РАБОТЫ С OpenAI (Beta)
# -----------------------------------------------------------------------------



class OpenAIClientAsync:
    """
    Асинхронный клиент для работы с OpenAI Assistants API (https://platform.openai.com/docs/api-reference/assistants).
    Поддерживает ассистентов, threads, messages, runs, steps, файлы, инструменты.
    Все методы асинхронные через asyncio.to_thread.
    Пример использования:
        client = OpenAIClientAsync(api_key, assistant_id, logger)
        thread_id = await client.create_thread()
        await client.send_message(thread_id, 'Привет!')
        run_id = await client.run_assistant(thread_id)
        answer = await client.poll_run_steps(thread_id, run_id, chat_id, bot)
    """
    def __init__(self, api_key: str, assistant_id: str, logger: logging.Logger):
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        self.logger = logger

    # ---------- ASSISTANTS CRUD ----------
    async def create_assistant(self, **kwargs) -> Optional[Any]:
        """Создать нового ассистента."""
        try:
            assistant = await asyncio.to_thread(self.client.beta.assistants.create, **kwargs)
            self.logger.info(f"Создан ассистент: {assistant.id}")
            return assistant
        except Exception as e:
            self.logger.error(f"Ошибка создания ассистента: {e}")
            return None

    async def retrieve_assistant(self, assistant_id: str) -> Optional[Any]:
        """Получить ассистента по ID."""
        try:
            return await asyncio.to_thread(self.client.beta.assistants.retrieve, assistant_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения ассистента: {e}")
            return None

    async def update_assistant(self, assistant_id: str, **kwargs) -> Optional[Any]:
        """Обновить ассистента."""
        try:
            return await asyncio.to_thread(self.client.beta.assistants.update, assistant_id, **kwargs)
        except Exception as e:
            self.logger.error(f"Ошибка обновления ассистента: {e}")
            return None

    async def delete_assistant(self, assistant_id: str) -> bool:
        """Удалить ассистента."""
        try:
            await asyncio.to_thread(self.client.beta.assistants.delete, assistant_id)
            self.logger.info(f"Ассистент {assistant_id} удалён")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления ассистента: {e}")
            return False

    async def list_assistants(self) -> list:
        """Список ассистентов."""
        try:
            page = await asyncio.to_thread(self.client.beta.assistants.list)
            return list(page)
        except Exception as e:
            self.logger.error(f"Ошибка получения списка ассистентов: {e}")
            return []

    # ---------- THREADS ----------
    async def create_thread(self) -> Optional[str]:
        """Создать новый thread и вернуть его ID."""
        try:
            thread_obj = await asyncio.to_thread(self.client.beta.threads.create)
            self.logger.info(f"Создан новый thread с id: {thread_obj.id}")
            return thread_obj.id
        except Exception as e:
            self.logger.exception("Ошибка при создании thread.")
            return None

    async def retrieve_thread(self, thread_id: str) -> Optional[Any]:
        try:
            return await asyncio.to_thread(self.client.beta.threads.retrieve, thread_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения thread: {e}")
            return None

    async def delete_thread(self, thread_id: str) -> bool:
        try:
            await asyncio.to_thread(self.client.beta.threads.delete, thread_id)
            self.logger.info(f"Thread {thread_id} удалён")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления thread: {e}")
            return False

    # ---------- MESSAGES ----------
    async def send_message(self, thread_id: str, message: str, role: str = "user") -> bool:
        """Отправить сообщение в thread (user/assistant)."""
        try:
            await asyncio.to_thread(
                self.client.beta.threads.messages.create,
                thread_id=thread_id,
                role=role,
                content=message,
            )
            self.logger.info(f"Сообщение ({role}) отправлено в thread {thread_id}")
            return True
        except Exception as e:
            self.logger.exception(f"Ошибка при отправке сообщения в thread {thread_id}.")
            return False

    async def list_messages(self, thread_id: str) -> list:
        try:
            page = await asyncio.to_thread(self.client.beta.threads.messages.list, thread_id)
            return list(page)
        except Exception as e:
            self.logger.error(f"Ошибка получения сообщений: {e}")
            return []

    async def retrieve_message(self, thread_id: str, message_id: str) -> Any:
        try:
            return await asyncio.to_thread(
                self.client.beta.threads.messages.retrieve,
                thread_id=thread_id,
                message_id=message_id,
            )
        except Exception as e:
            self.logger.exception(f"Ошибка при извлечении сообщения {message_id} из thread {thread_id}.")
            return None

    # ---------- RUNS ----------
    async def run_assistant(self, thread_id: str, tools: Optional[list] = None) -> Optional[str]:
        """Запустить ассистента на thread. tools — список инструментов (code_interpreter, retrieval, function)."""
        try:
            kwargs = dict(assistant_id=self.assistant_id, thread_id=thread_id)
            if tools:
                kwargs["tools"] = tools
            run_obj = await asyncio.to_thread(self.client.beta.threads.runs.create, **kwargs)
            self.logger.info(f"Создан run {run_obj.id} для thread {thread_id}")
            return run_obj.id
        except Exception as e:
            self.logger.exception(f"Ошибка при создании run для thread {thread_id}.")
            return None

    async def retrieve_run(self, thread_id: str, run_id: str) -> Any:
        try:
            return await asyncio.to_thread(self.client.beta.threads.runs.retrieve, thread_id=thread_id, run_id=run_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения run: {e}")
            return None

    async def list_runs(self, thread_id: str) -> list:
        try:
            page = await asyncio.to_thread(self.client.beta.threads.runs.list, thread_id=thread_id)
            return list(page)
        except Exception as e:
            self.logger.error(f"Ошибка получения списка runs: {e}")
            return []

    # ---------- STEPS ----------
    async def get_run_steps(self, thread_id: str, run_id: str) -> list:
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

    # ---------- FILES ----------
    async def upload_file(self, file_path: str, purpose: str = "assistants") -> Optional[str]:
        """Загрузить файл для ассистента/инструмента."""
        try:
            with open(file_path, "rb") as f:
                file_obj = await asyncio.to_thread(self.client.files.create, file=f, purpose=purpose)
            self.logger.info(f"Файл {file_obj.id} загружен для {purpose}")
            return file_obj.id
        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return None

    async def list_files(self, purpose: Optional[str] = None) -> list:
        try:
            page = await asyncio.to_thread(self.client.files.list, purpose=purpose) if purpose else await asyncio.to_thread(self.client.files.list)
            return list(page)
        except Exception as e:
            self.logger.error(f"Ошибка получения списка файлов: {e}")
            return []

    async def retrieve_file(self, file_id: str) -> Any:
        try:
            return await asyncio.to_thread(self.client.files.retrieve, file_id)
        except Exception as e:
            self.logger.error(f"Ошибка получения файла: {e}")
            return None

    async def delete_file(self, file_id: str) -> bool:
        try:
            await asyncio.to_thread(self.client.files.delete, file_id)
            self.logger.info(f"Файл {file_id} удалён")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления файла: {e}")
            return False

    # ---------- HELPERS ----------
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

    async def poll_run_steps(
        self,
        thread_id: str,
        run_id: str,
        chat_id: int,
        bot: Bot,
        max_attempts: int = 20,
        interval: int = 1,
    ) -> str:
        """Ожидаем появления ответа ассистента."""
        final_answer: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            try:
                await bot.send_chat_action(chat_id, action="typing")
            except Exception:
                pass

            steps = await self.get_run_steps(thread_id, run_id)
            for step in steps:
                details = getattr(step, "step_details", None)
                if details and getattr(details, "type", "") == "message_creation":
                    msg_id = getattr(details.message_creation, "message_id", None)
                    if msg_id:
                        msg_obj = await self.retrieve_message(thread_id, msg_id)
                        if msg_obj:
                            content = getattr(msg_obj, "content", None)
                            final_answer = self.extract_text_from_content(content)
                            if final_answer and final_answer.strip():
                                self.logger.info(
                                    f"Ответ ассистента получен на попытке {attempt}."
                                )
                                return final_answer

            await asyncio.sleep(interval)

        return (
            final_answer
            or "❗️ Не удалось получить ответ от ассистента. Попробуйте позже."
        )

    async def process_user_request(self, thread_id: str, user_question: str, chat_id: int, bot: Bot, tools: Optional[list] = None) -> str:
        ok = await self.send_message(thread_id, user_question)
        if not ok:
            return "❗️ Ошибка при отправке сообщения. Попробуйте позже."
        run_id = await self.run_assistant(thread_id, tools=tools)
        if not run_id:
            return "❗️ Ошибка при запуске ассистента. Попробуйте позже."
        final_answer = await self.poll_run_steps(thread_id, run_id, chat_id=chat_id, bot=bot)
        return final_answer

# Инициализация асинхронного клиента
openai_client_async = OpenAIClientAsync(api_key=OPENAI_API_KEY, assistant_id=ASSISTANT_ID, logger=logger)



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
            thread_id = await openai_client_async.create_thread()
            if not thread_id:
                await message.answer("Ошибка: не получен thread ID от OpenAI.")
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
        f"Твой thread ID: <code>{thread_id}</code>\n"
        f"Задай вопрос командой: /ask &lt;твой вопрос&gt;\n"
        f"Команда /help покажет все доступные действия."
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Показываем справку по командам."""
    help_text = (
        "Доступные команды:\n"
        "/start - начать работу с ботом\n"
        "/ask &lt;вопрос&gt; - задать вопрос ассистенту\n"
        "/reset - начать новый диалог"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Сбросить текущий диалог и создать новый thread."""
    user_id = message.from_user.id
    try:
        thread_id = await openai_client_async.create_thread()
        if not thread_id:
            await message.answer("Ошибка: не удалось создать новый thread.")
            return
        user_threads[user_id] = thread_id
        await message.answer(
            "Начинаем новый диалог. Можешь задать вопрос командой /ask",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.exception("Ошибка при сбросе диалога")
        await message.answer(f"Ошибка сброса: {e}")

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
    await message.answer("Секунду, думаю…")

    try:
        answer = await openai_client_async.process_user_request(thread_id, user_question, message.chat.id, bot)
        # Удаляем все <br> и <br/> для Telegram
        import re
        answer = re.sub(r'<br\s*/?>', '\n', answer)
        await message.answer(
            f"Ответ ассистента:\n\n{answer}\n\n"
            "Задай новый вопрос командой /ask или перезапусти диалог /reset.",
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.exception("Ошибка при получении ответа от ассистента.")
        await message.answer(f"Произошла ошибка: {e}", parse_mode=ParseMode.HTML)


@router.message(lambda message: message.content_type == "text")
async def handle_text_messages(message: types.Message):
    """
    Обработчик любых текстовых сообщений, которые не являются командами.
    """
    if message.text.startswith("/"):
        await message.answer(
            "Неизвестная команда. Используйте /help для списка команд."
        )
    else:
        await message.answer(
            "Вы отправили сообщение без команды. Используйте /ask <вопрос> "
            "или посмотрите справку командой /help."
        )

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
    logger.info("Запускаем Telegram-бота на aiogram v3.x...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
