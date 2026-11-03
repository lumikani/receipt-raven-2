"""The local OCR analyzer against a scripted chat completions endpoint."""

import base64
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest

from src.application.analysis.protocols.receipt_analyzer import ReceiptAnalysisError
from src.config import Settings
from src.infrastructure.analysis.analyzer_factory import build_receipt_analyzer
from src.infrastructure.analysis.local_ocr.analyzer import LocalOCRAnalyzer

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ocr"

MODEL = "richardyoung/lightonocr-3-4b:Q4_K_M"


def herkkuduo_content() -> str:
    envelope = json.loads((FIXTURES / "herkkuduo_grounding_response.json").read_text("utf-8"))
    return str(envelope["choices"][0]["message"]["content"])


def completion(content: str | None) -> httpx.Response:
    message: dict[str, object] = {"role": "assistant"}
    if content is not None:
        message["content"] = content
    return httpx.Response(200, json={"model": MODEL, "choices": [{"message": message}]})


def analyzer(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[LocalOCRAnalyzer, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    return LocalOCRAnalyzer(
        base_url="http://localhost:11434/v1",
        model=MODEL,
        timeout_seconds=120,
        transport=httpx.MockTransport(handle),
    ), requests


async def test_sends_the_locked_request_shape_and_parses_the_answer() -> None:
    subject, requests = analyzer(lambda request: completion(herkkuduo_content()))

    result = await subject.analyze(b"\xff\xd8photo", "image/jpeg", ["Expenses:Food"])

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/v1/chat/completions"
    assert "Authorization" not in request.headers
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["think"] is False
    assert body["reasoning_effort"] == "none"
    assert body["temperature"] == 0.2
    assert body["top_p"] == 0.9
    assert body["max_tokens"] == 4096
    assert "response_format" not in body
    image_part, text_part = body["messages"][0]["content"]
    assert image_part["type"] == "image_url"
    expected_url = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8photo").decode("ascii")
    assert image_part["image_url"]["url"] == expected_url
    assert text_part == {"type": "text", "text": "grounding"}

    assert result.payee == "Herkkuduo"
    assert result.receipt_date == date(2026, 5, 12)
    assert result.total == 11.76
    assert result.currency == "EUR"
    assert result.model == MODEL
    assert result.card_last_digits == "9841"
    assert [p.name for p in result.products] == [
        "Banaani 2 kpl 3,99 €",
        "Maito 1 l 1,29 €",
        "Leipä 400 g 2,49 €",
    ]
    assert all(p.expense_account == "" for p in result.products)


async def test_pdf_is_rejected_with_a_photo_message_and_no_request() -> None:
    subject, requests = analyzer(lambda request: completion(herkkuduo_content()))

    with pytest.raises(ReceiptAnalysisError, match="JPEG/PNG photo"):
        await subject.analyze(b"%PDF", "application/pdf", [])

    assert requests == []


async def test_empty_content_is_an_analysis_error() -> None:
    subject, _ = analyzer(lambda request: completion(""))

    with pytest.raises(ReceiptAnalysisError, match="No content"):
        await subject.analyze(b"x", "image/png", [])


async def test_missing_choices_is_an_analysis_error() -> None:
    subject, _ = analyzer(lambda request: httpx.Response(200, json={"choices": []}))

    with pytest.raises(ReceiptAnalysisError, match="No content"):
        await subject.analyze(b"x", "image/png", [])


async def test_http_error_carries_status_and_truncated_body() -> None:
    long_body = "boom " + "x" * 1000
    subject, _ = analyzer(lambda request: httpx.Response(500, text=long_body))

    with pytest.raises(ReceiptAnalysisError) as exc_info:
        await subject.analyze(b"x", "image/png", [])

    message = str(exc_info.value)
    assert "500" in message
    assert "boom" in message
    assert "x" * 1000 not in message  # body truncated to 500 chars


async def test_connection_failure_is_an_analysis_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    subject, _ = analyzer(fail)

    with pytest.raises(ReceiptAnalysisError, match="not reachable"):
        await subject.analyze(b"x", "image/png", [])


async def test_timeout_is_an_analysis_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    subject, _ = analyzer(fail)

    with pytest.raises(ReceiptAnalysisError, match="timed out after 120 seconds"):
        await subject.analyze(b"x", "image/png", [])


async def test_non_json_200_answer_is_an_analysis_error() -> None:
    subject, _ = analyzer(lambda request: httpx.Response(200, text="<html>not json</html>"))

    with pytest.raises(ReceiptAnalysisError):
        await subject.analyze(b"x", "image/png", [])


def test_factory_builds_the_local_analyzer_from_settings() -> None:
    settings = Settings(AI_PROVIDER="local", AI_TIMEOUT_SECONDS=42)

    subject = build_receipt_analyzer(settings)

    assert isinstance(subject, LocalOCRAnalyzer)
    assert subject.base_url == settings.LOCAL_BASE_URL == "http://localhost:11434/v1"
    assert subject.model == settings.LOCAL_MODEL == MODEL
    assert subject.timeout == 42  # reuses the existing AI timeout setting
