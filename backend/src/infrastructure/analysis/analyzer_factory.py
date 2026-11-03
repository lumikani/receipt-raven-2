"""Choose the receipt analyzer the settings ask for."""

from src.application.analysis.protocols.receipt_analyzer import ReceiptAnalyzerProtocol
from src.config import Settings
from src.infrastructure.analysis.mock_analyzer import MockReceiptAnalyzer
from src.infrastructure.analysis.openai_compatible_analyzer import (
    OpenAICompatibleReceiptAnalyzer,
)


def build_receipt_analyzer(settings: Settings) -> ReceiptAnalyzerProtocol:
    """`AI_PROVIDER`: openrouter (default), openai, mock or local."""
    match settings.AI_PROVIDER:
        case "openrouter":
            return OpenAICompatibleReceiptAnalyzer(
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY,
                model=settings.OPENROUTER_MODEL,
                timeout_seconds=settings.AI_TIMEOUT_SECONDS,
                structured_output=True,
            )
        case "openai":
            return OpenAICompatibleReceiptAnalyzer(
                base_url=settings.OPENAI_BASE_URL,
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
                timeout_seconds=settings.AI_TIMEOUT_SECONDS,
                structured_output=False,
            )
        case "mock":
            return MockReceiptAnalyzer(delay_seconds=settings.AI_MOCK_DELAY_SECONDS)
        case "local":
            # LocalOCRAnalyzer (infrastructure/analysis/local_ocr/) lands with
            # its implementation; until then fail loudly instead of falling
            # back to a cloud provider.
            raise NotImplementedError(
                "AI_PROVIDER=local requires the local OCR analyzer "
                "(infrastructure/analysis/local_ocr/), which is not part of "
                "this build; use openrouter, openai or mock."
            )
