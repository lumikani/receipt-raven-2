"""Receipt analysis through a local ollama-compatible `/v1` endpoint.

The request envelope is locked to what the local OCR model expects (see
`.agents/docs/local-ocr-models.md`): the `grounding` prompt, no
`response_format`, documents as `image_url` data URIs only, and no
`Authorization` header. PDFs are rejected — the model reads pixels only, so
the user is told to upload a JPEG/PNG photo instead.
"""

import base64
from typing import Any

import httpx
import structlog

from src.application.analysis.protocols.receipt_analyzer import (
    ReceiptAnalysis,
    ReceiptAnalysisError,
)
from src.infrastructure.analysis.local_ocr.parser import parse_ocr_output

logger = structlog.get_logger(__name__)

# Locked request constants for the local OCR model (LightOnOCR and siblings).
PROMPT = "grounding"
TEMPERATURE = 0.2
TOP_P = 0.9
MAX_TOKENS = 4096

PDF_REJECTION = (
    "The local OCR provider reads photos only: "
    "upload a JPEG/PNG photo of the receipt instead of a PDF."
)


class LocalOCRAnalyzer:
    """Sends the receipt photo to `{base_url}/chat/completions` on the host."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout_seconds
        self.transport = transport

    def _request_body(self, document: bytes, mime_type: str) -> dict[str, Any]:
        data_url = f"data:{mime_type};base64,{base64.b64encode(document).decode('ascii')}"
        return {
            "model": self.model,
            "think": False,
            "reasoning_effort": "none",
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        }

    async def analyze(
        self, document: bytes, mime_type: str, expense_accounts: list[str]
    ) -> ReceiptAnalysis:
        """Read the receipt photo. `expense_accounts` is accepted but ignored:
        the local model cannot choose accounts — the rule engine does."""
        if mime_type == "application/pdf":
            raise ReceiptAnalysisError(PDF_REJECTION)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=self._request_body(document, mime_type),
                )
                response.raise_for_status()
            body: Any = response.json()
        except httpx.HTTPStatusError as exc:
            raise ReceiptAnalysisError(
                f"Local OCR provider answered {exc.response.status_code}: {exc.response.text[:500]}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ReceiptAnalysisError(
                f"Local OCR provider timed out after {self.timeout} seconds"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError: a 200 answer whose body is not JSON.
            raise ReceiptAnalysisError(f"Local OCR provider not reachable: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ReceiptAnalysisError("No content in the local OCR provider's answer") from exc
        if not content:
            raise ReceiptAnalysisError("No content in the local OCR provider's answer")
        logger.info("receipt_analysed", model=self.model)
        return parse_ocr_output(str(content), self.model)
