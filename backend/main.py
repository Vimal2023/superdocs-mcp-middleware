from __future__ import annotations

import io
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

SUPERDOCS_API_BASE: str = os.getenv(
    "SUPERDOCS_API_BASE", "https://api.superdocs.app/v1"
)
SUPERDOCS_API_KEY: str = os.getenv("SUPERDOCS_API_KEY", "")

if not SUPERDOCS_API_KEY:
    logger.warning(
        "SUPERDOCS_API_KEY is not set.  "
        "Set it in backend/.env before making report-generation requests."
    )

REPORT_INSTRUCTION: str = (
    "Transform these rough notes into a highly polished, professional HTML report. "
    "STRICT STYLING RULES THAT MUST BE FOLLOWED EVERY TIME: "
    "1. Start with a full-width header <div> with a dark blue background (#2c3e50), white text, 30px padding, and an uppercase H1 title. "
    "2. Below the header, add a clean meta-information table (Report ID, Date, Prepared For, Prepared By) using highlighted <mark> placeholders where data is missing. "
    "3. Format the rest of the document with clean H2 headings (dark blue text with a 2px solid bottom border), bullet points, and well-spaced paragraphs (line-height: 1.6). "
    "4. Output ONLY the final document content with these exact inline HTML styles."
)

# Timeout seconds for outbound HTTP calls to the SuperDocs API.
HTTP_TIMEOUT: float = 60.0

class NotesInput(BaseModel):
    """Payload accepted by the /api/generate-report endpoint."""

    raw_text: str = Field(
        ...,
        min_length=1,
        description="Unstructured raw notes to be transformed into a report.",
        examples=["Meeting notes: discussed Q3 roadmap, hiring plan, budget."],
    )


class ReportResponse(BaseModel):
    """Successful response returned to the client."""

    report: str = Field(
        ...,
        description="Formatted Markdown report produced by SuperDocs.",
    )


class ErrorDetail(BaseModel):
    """Structured error detail for non-2xx responses."""

    detail: str


class ExportInput(BaseModel):
    """Payload accepted by the /api/export-pdf endpoint."""

    html: str

app = FastAPI(
    title="SuperDocs Report Agent",
    description=(
        "Middleware service that converts raw notes into a structured "
        "Markdown report via the SuperDocs AI API."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Replace with explicit origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_superdocs_headers() -> dict[str, str]:
    """Return the HTTP headers required by the SuperDocs API."""
    return {
        "Authorization": f"Bearer {SUPERDOCS_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _build_superdocs_payload(raw_text: str) -> dict[str, Any]:
    """
    Construct the JSON body for the SuperDocs /v1/chat endpoint.

    SuperDocs /v1/chat payload structure:
      {
        "message":       "<instruction for the AI>",
        "session_id":    "<opaque session identifier>",
        "document_html": "<raw source material to load into the session>"
      }

    We pass REPORT_INSTRUCTION as the chat `message` so the model knows the
    desired transformation, and supply the raw notes via `document_html` so
    SuperDocs loads them into the editing session for the first turn.
    """
    return {
        "message": REPORT_INSTRUCTION,
        "session_id": "report-gen-session",
        "document_html": raw_text,
    }


async def _call_superdocs(raw_text: str) -> str:
    """
    Make an async POST request to the SuperDocs /v1/chat endpoint and return
    the edited document content as a string.

    SuperDocs endpoint used:
      POST {SUPERDOCS_API_BASE}/chat

    The API responds with the transformed content inside:
      data["document_changes"]["updated_html"]
    with a fallback to data["response"] for plain-text replies.

    Raises:
        HTTPException(502): When the SuperDocs API returns a non-2xx status.
        HTTPException(504): When the request times out.
        HTTPException(502): For any unexpected network-level error.
    """
    url = f"{SUPERDOCS_API_BASE}/chat"
    headers = _build_superdocs_headers()
    payload = _build_superdocs_payload(raw_text)

    logger.info("Calling SuperDocs API | url=%s", url)

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

        logger.info(
            "SuperDocs responded | status=%s", response.status_code
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        document_changes = data.get("document_changes", {})
        report_content: str = document_changes.get("updated_html") or data.get("response") or ""

        if not report_content:
            logger.error(
                "SuperDocs returned an empty report body. Full response: %s",
                data,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "SuperDocs returned a successful status but an empty "
                    "report body.  Check the API response schema."
                ),
            )

        return report_content

    except httpx.TimeoutException as exc:
        logger.exception("SuperDocs request timed out after %.1fs", HTTP_TIMEOUT)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"SuperDocs API timed out after {HTTP_TIMEOUT}s.",
        ) from exc

    except httpx.HTTPStatusError as exc:
        error_body = exc.response.text
        logger.error(
            "SuperDocs returned %s | body=%s",
            exc.response.status_code,
            error_body,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"SuperDocs API error {exc.response.status_code}: {error_body}"
            ),
        ) from exc

    except httpx.RequestError as exc:
        logger.exception("Network error while contacting SuperDocs")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach the SuperDocs API: {exc}",
        ) from exc

@app.get("/health", tags=["Utility"])
async def health_check() -> dict[str, str]:
    """Lightweight liveness probe for container orchestration / load balancers."""
    return {"status": "ok"}


@app.post(
    "/api/generate-report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a structured Markdown report from raw notes",
    tags=["Reports"],
)
async def generate_report(notes: NotesInput) -> ReportResponse:
    """
    Accept raw, unstructured notes and return a professionally formatted
    Markdown report generated by the SuperDocs AI pipeline.

    **Request body**
    ```json
    { "raw_text": "Meeting notes: Q3 budget is $120k ..." }
    ```

    **Response body**
    ```json
    { "report": "# Executive Summary\\n..." }
    ```
    """
    if not SUPERDOCS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SUPERDOCS_API_KEY is not configured on the server.  "
                "Set it in backend/.env and restart the service."
            ),
        )

    logger.info(
        "generate_report called | raw_text_length=%d chars",
        len(notes.raw_text),
    )

    report_markdown = await _call_superdocs(notes.raw_text)

    logger.info(
        "Report generated successfully | report_length=%d chars",
        len(report_markdown),
    )

    return ReportResponse(report=report_markdown)


@app.post(
    "/api/export-pdf",
    status_code=status.HTTP_200_OK,
    summary="Export an HTML report as a high-fidelity PDF via SuperDocs",
    tags=["Reports"],
)
async def export_pdf(payload: ExportInput) -> StreamingResponse:
    """
    Accept an HTML string and return a PDF binary produced by the SuperDocs
    native high-fidelity export endpoint.

    **Request body**
    ```json
    { "html": "<h1>My Report</h1>..." }
    ```

    **Response**: Binary PDF stream with
    ``Content-Disposition: attachment; filename=SuperDocs_Report.pdf``.
    """
    if not SUPERDOCS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SUPERDOCS_API_KEY is not configured on the server.  "
                "Set it in backend/.env and restart the service."
            ),
        )

    url = f"{SUPERDOCS_API_BASE}/documents/export"
    headers = _build_superdocs_headers()
    body = {
        "html": payload.html,
        "format": "pdf",
        "options": {"paper_size": "A4", "margins": "normal"},
    }

    logger.info("Calling SuperDocs export API | url=%s", url)

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=body)

        logger.info(
            "SuperDocs export responded | status=%s", response.status_code
        )

        response.raise_for_status()

        return StreamingResponse(
            io.BytesIO(response.content),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=SuperDocs_Report.pdf"},
        )

    except httpx.TimeoutException as exc:
        logger.exception("SuperDocs export request timed out after %.1fs", HTTP_TIMEOUT)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"SuperDocs export API timed out after {HTTP_TIMEOUT}s.",
        ) from exc

    except httpx.HTTPStatusError as exc:
        error_body = exc.response.text
        logger.error(
            "SuperDocs export returned %s | body=%s",
            exc.response.status_code,
            error_body,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"SuperDocs export API error {exc.response.status_code}: {error_body}"
            ),
        ) from exc

    except httpx.RequestError as exc:
        logger.exception("Network error while contacting SuperDocs export endpoint")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach the SuperDocs export API: {exc}",
        ) from exc

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
