import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import main  # noqa: E402
from ai_service import AiServiceBase, NoOpAiService  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from storage import Storage  # noqa: E402


class FakeAi(AiServiceBase):
    """Answers every prompt with a fixed response."""

    def __init__(self, response):
        self.response = response
        self.prompts = []

    async def complete(self, prompt):
        self.prompts.append(prompt)
        return self.response


@pytest.fixture
def storage(tmp_path, monkeypatch):
    store = Storage(tmp_path)
    monkeypatch.setattr(main, "storage", store)
    monkeypatch.setattr(main, "ai_service", NoOpAiService())
    return store


@pytest.fixture
def client(storage):
    with TestClient(main.app) as c:  # runs startup, which seeds default categories
        yield c


@pytest.fixture
def fake_ai(monkeypatch):
    def install(response):
        ai = FakeAi(response)
        monkeypatch.setattr(main, "ai_service", ai)
        return ai
    return install
