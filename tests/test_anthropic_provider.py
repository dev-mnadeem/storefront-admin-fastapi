"""The Anthropic briefing writer, exercised offline.

A stand-in ``anthropic`` module replaces the SDK, so these tests need neither
the optional package nor a network connection nor a key.
"""

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.ai.factory import build_provider
from app.core.config import Settings
from tests.test_insights import METRICS


class FakeMessages:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=self.reply),
            ]
        )


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> FakeMessages:
    messages = FakeMessages(
        "Revenue is up 50% on last month.\n"
        "- Gadgets brought in 150.00.\n"
        "ignored line without a bullet\n"
        "- Gizmo X is down to 5 units."
    )

    class FakeAsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = messages

    module = ModuleType("anthropic")
    module.AsyncAnthropic = FakeAsyncAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.delitem(sys.modules, "app.ai.anthropic_provider", raising=False)
    return messages


def _settings() -> Settings:
    return Settings(
        insight_provider="anthropic",
        anthropic_api_key="offline-test-key",
        anthropic_model="claude-opus-5",
    )


@pytest.mark.asyncio
async def test_provider_sends_the_metrics_and_parses_the_reply(
    fake_sdk: FakeMessages,
) -> None:
    provider = build_provider(_settings())
    assert provider.name == "anthropic"

    result = await provider.write(METRICS)

    assert result.headline == "Revenue is up 50% on last month."
    assert result.bullets == [
        "Gadgets brought in 150.00.",
        "Gizmo X is down to 5 units.",
    ]
    (call,) = fake_sdk.calls
    assert call["model"] == "claude-opus-5"
    sent = json.loads(call["messages"][0]["content"])
    assert sent["current_period_revenue"] == 150.0


@pytest.mark.asyncio
async def test_an_empty_reply_is_an_error_the_service_can_fall_back_from(
    fake_sdk: FakeMessages,
) -> None:
    fake_sdk.reply = "  \n"
    with pytest.raises(ValueError, match="empty briefing"):
        await build_provider(_settings()).write(METRICS)


def test_factory_falls_back_when_the_package_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.delitem(sys.modules, "app.ai.anthropic_provider", raising=False)
    assert build_provider(_settings()).name == "rules"
