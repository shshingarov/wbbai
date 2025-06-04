import sys
import types
from unittest.mock import AsyncMock, patch

import pytest

# Provide dummy aiogram module to import run.py without installing aiogram
aiogram_dummy = types.ModuleType("aiogram")
aiogram_dummy.Bot = type("Bot", (), {"__init__": lambda self, *a, **k: None, "send_chat_action": lambda self, *a, **k: None})
aiogram_dummy.Dispatcher = type("Dispatcher", (), {"__init__": lambda self, *a, **k: None, "include_router": lambda self, *a, **k: None, "start_polling": lambda self, *a, **k: None})
aiogram_dummy.types = types.SimpleNamespace(Message=object)
aiogram_dummy.Router = type("Router", (), {"__init__": lambda self, *a, **k: None, "message": lambda self, *a, **k: (lambda func: func)})
aiogram_dummy.filters = types.ModuleType("filters")
aiogram_dummy.filters.Command = lambda *a, **k: object()
aiogram_dummy.enums = types.ModuleType("enums")
aiogram_dummy.enums.ParseMode = object

sys.modules.setdefault("aiogram", aiogram_dummy)
sys.modules.setdefault("aiogram.filters", aiogram_dummy.filters)
sys.modules.setdefault("aiogram.enums", aiogram_dummy.enums)

# Dummy openai module
openai_dummy = types.ModuleType("openai")

class DummyOpenAI:
    def __init__(self, *_, **__):
        self.beta = types.SimpleNamespace(
            threads=types.SimpleNamespace(
                create=lambda *a, **k: types.SimpleNamespace(id="tid"),
                messages=types.SimpleNamespace(create=lambda *a, **k: None),
                runs=types.SimpleNamespace(create=lambda *a, **k: types.SimpleNamespace(id="rid")),
            ),
            assistants=types.SimpleNamespace(),
            files=types.SimpleNamespace(),
        )

openai_dummy.OpenAI = DummyOpenAI
sys.modules.setdefault("openai", openai_dummy)

# Dummy nest_asyncio module
nest_asyncio_dummy = types.ModuleType("nest_asyncio")
nest_asyncio_dummy.apply = lambda: None
sys.modules.setdefault("nest_asyncio", nest_asyncio_dummy)


from run import OpenAIClientAsync


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


@pytest.fixture
def client():
    return OpenAIClientAsync(api_key="key", assistant_id="asst", logger=DummyLogger())


@pytest.mark.asyncio
async def test_create_thread(client):
    with patch.object(client.client.beta.threads, "create", return_value=types.SimpleNamespace(id="id")) as mock_create:
        thread_id = await client.create_thread()
        mock_create.assert_called_once()
        assert thread_id == mock_create.return_value.id


@pytest.mark.asyncio
async def test_send_message(client):
    with patch.object(client.client.beta.threads.messages, "create", return_value=None) as mock_send:
        ok = await client.send_message("thread", "hi")
        mock_send.assert_called_once()
        assert ok


@pytest.mark.asyncio
async def test_run_assistant(client):
    run_obj = types.SimpleNamespace(id="run")
    with patch.object(client.client.beta.threads.runs, "create", return_value=run_obj) as mock_run:
        run_id = await client.run_assistant("thread")
        mock_run.assert_called_once()
        assert run_id == "run"
