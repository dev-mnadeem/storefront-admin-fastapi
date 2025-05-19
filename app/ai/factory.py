import logging

from app.ai.base import InsightProvider
from app.ai.rules import RuleBasedInsightProvider
from app.core.config import Settings

logger = logging.getLogger(__name__)


def build_provider(settings: Settings) -> InsightProvider:
    """Pick a briefing writer, degrading to the deterministic one."""
    if settings.insight_provider != "anthropic":
        return RuleBasedInsightProvider()

    if not settings.anthropic_api_key:
        logger.warning(
            "INSIGHT_PROVIDER=anthropic but ANTHROPIC_API_KEY is unset - "
            "using the rule-based briefing."
        )
        return RuleBasedInsightProvider()

    try:
        # Imported lazily so the package stays an optional dependency.
        from app.ai.anthropic_provider import (  # noqa: PLC0415
            AnthropicInsightProvider,
        )
    except ImportError:
        logger.warning(
            "INSIGHT_PROVIDER=anthropic but the 'anthropic' package is not "
            "installed - using the rule-based briefing."
        )
        return RuleBasedInsightProvider()

    return AnthropicInsightProvider(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
        max_tokens=settings.insight_max_tokens,
    )
