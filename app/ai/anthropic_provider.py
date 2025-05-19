"""Optional briefing writer backed by the Anthropic Messages API.

Enable with ``INSIGHT_PROVIDER=anthropic`` and ``ANTHROPIC_API_KEY``. The
model is handed the same measured figures the rule-based writer uses and is
asked only to phrase them, which keeps the numbers out of its hands.
"""

import json

from anthropic import AsyncAnthropic

from app.ai.base import ProviderResult
from app.schemas.insights import InsightMetrics

SYSTEM_PROMPT = (
    "You write the opening briefing on a storefront admin dashboard. "
    "You are given measured figures as JSON. Use only those figures - never "
    "invent or recompute a number. Reply with a single headline sentence on "
    "the first line, then two to four lines each starting with '- '. "
    "No preamble, no markdown headings."
)

BULLET_PREFIX = "- "


class AnthropicInsightProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def write(self, metrics: InsightMetrics) -> ProviderResult:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(metrics.model_dump(mode="json")),
                }
            ],
        )
        text = "\n".join(
            block.text for block in response.content if block.type == "text"
        )
        return _parse(text)


def _parse(text: str) -> ProviderResult:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("the model returned an empty briefing")
    headline = lines[0]
    bullets = [
        line.removeprefix(BULLET_PREFIX).strip()
        for line in lines[1:]
        if line.startswith(BULLET_PREFIX)
    ]
    return ProviderResult(headline=headline, bullets=bullets)
