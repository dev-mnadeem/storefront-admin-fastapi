"""Pluggable writers for the daily briefing.

The rule-based provider is the default and needs no network, no key and no
extra dependency. The Anthropic provider is opt-in and falls back to the
rule-based text on any failure, so the endpoint always answers.
"""

from app.ai.base import InsightProvider, ProviderResult
from app.ai.factory import build_provider
from app.ai.rules import RuleBasedInsightProvider

__all__ = [
    "InsightProvider",
    "ProviderResult",
    "RuleBasedInsightProvider",
    "build_provider",
]
