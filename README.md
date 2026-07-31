# SuperDocs Report Agent

> A full-stack middleware agent that converts raw, unstructured notes into polished, structured HTML reports and native PDFs — powered entirely by the [SuperDocs](https://superdocs.app) AI engine.

---

## Overview

**SuperDocs Report Agent** is a production-grade, full-stack middleware application built to demonstrate an autonomous agentic workflow using the SuperDocs REST API. The agent accepts raw, disorganised meeting notes or plain text through a split-screen web UI, orchestrates the SuperDocs AI pipeline to produce a highly polished, SaaS-grade HTML report, and optionally exports it as a pixel-perfect, print-ready PDF — all in a single, seamless flow.

This project was purpose-built to test the depth and flexibility of the SuperDocs API surface, specifically its chat-based document transformation and high-fidelity native export capabilities.

---

## How the SuperDocs API is Leveraged

This is the heart of the agent. Two distinct SuperDocs endpoints are integrated to form a complete document automation pipeline.

### 1. `POST /v1/chat` — AI Formatting Engine

The `/v1/chat` endpoint is used as the **core document transformation engine**. The FastAPI backend constructs a precise payload that bundles the user's raw notes with a highly strict system prompt. This prompt enforces a consistent SaaS-style output aesthetic:

- Dark-blue (`#2c3e50`) section headers with bold hierarchy
- Meta-information tables (date, author, version) at the top of every report
- Strict inline HTML styling for maximum render fidelity across any browser or PDF renderer
- Semantic structure: executive summary, numbered findings, and clearly delineated next-steps blocks

SuperDocs returns the transformed content inside `data["document_changes"]["updated_html"]`, with `data-chunk-id` attributes preserved throughout for potential downstream diff tracking. The agent falls back gracefully to `data["response"]` for plain-text replies.

```python
# Payload sent to /v1/chat
{
    "message":       REPORT_INSTRUCTION,   # Strict formatting prompt
    "session_id":    "report-gen-session",
    "document_html": raw_text              # User's unstructured notes
}
```

### 2. `POST /v1/documents/export` — High-Fidelity PDF Generation

Once the HTML report is rendered in the browser, the user can trigger the **Download PDF** flow. The agent takes the AI-generated HTML and streams it through the `/v1/documents/export` endpoint with the following options:

```python
# Payload sent to /v1/documents/export
{
    "html":    payload.html,
    "format":  "pdf",
    "options": {
        "paper_size": "A4",
        "margins":    "normal"
    }
}
```

The binary PDF response is piped directly back to the client via FastAPI's `StreamingResponse`, triggering an immediate browser download — no temporary files, no intermediate storage.

```
Client → POST /api/export-pdf → FastAPI → POST /v1/documents/export → SuperDocs
                                                                           ↓
Client ← binary PDF stream ← FastAPI ← StreamingResponse(io.BytesIO) ←───┘
```

### 3. Stateless Backend Authentication

The SuperDocs `sk_` API key is **never exposed to the frontend**. All authenticated requests are constructed and fired exclusively from the FastAPI backend using a centralised `_build_superdocs_headers()` helper. The frontend communicates only with the backend's local API over `localhost`, ensuring the secret key remains within the server trust boundary at all times.

---

## Architecture & Tech Stack

### Monorepo Structure

```
superdocs-report-agent/
├── backend/          # FastAPI service — orchestration, auth, streaming
│   ├── main.py
│   └── .env          # SUPERDOCS_API_KEY lives here (gitignored)
└── frontend/         # Next.js app — split-screen report UI
    ├── app/
    │   ├── page.tsx
    │   └── layout.tsx
    └── ...
```

### Frontend — `Next.js (App Router)`

| Technology                  | Role                                    |
| --------------------------- | --------------------------------------- |
| **Next.js 14** (App Router) | Framework & SSR boundary                |
| **React**                   | Component model & state management      |
| **Tailwind CSS**            | Utility-first styling                   |
| **Lucide React**            | Icon set (Sparkles, Download, Loader2…) |

The UI is intentionally designed as a **flush, edge-to-edge split-screen workspace** — raw notes on the left, live HTML report on the right — with zero wasted padding. This maximises usable document area and mirrors the density of professional document tools. The output panel renders the SuperDocs-generated HTML verbatim via `dangerouslySetInnerHTML`, preserving every inline style and structural element the AI produces.

### Backend — `FastAPI + Python`

| Technology        | Role                                  |
| ----------------- | ------------------------------------- |
| **FastAPI**       | Async REST API framework              |
| **HTTPX**         | Async HTTP client for SuperDocs calls |
| **Pydantic v2**   | Request/response validation & schema  |
| **Python-dotenv** | Secure environment variable loading   |
| **Uvicorn**       | ASGI server                           |

The backend is a **thin, fast, asynchronous orchestration layer**. Its sole responsibilities are:

- Enforcing CORS so the frontend can call it freely in development
- Structuring and validating inbound payloads from the UI
- Injecting the SuperDocs auth headers and forwarding requests upstream
- Streaming the binary PDF response back to the browser without buffering to disk

There is no database, no session store, and no business logic — keeping the service stateless, horizontally scalable, and trivially deployable.

---

## MCP Readiness & Future Scope

While the agent currently operates over a standard REST/HTTP transport, its core formatting and export logic is **intentionally modularised** behind clean async functions (`_call_superdocs`, `export_pdf`). This architecture makes it straightforward to wrap the same logic into an **MCP (Model Context Protocol) server**, enabling native use of the SuperDocs formatting and export pipeline directly inside AI-native IDEs such as **Cursor** or **Claude Desktop** — without any changes to the underlying SuperDocs integration layer.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- A SuperDocs API key (obtain one at [superdocs.app](https://superdocs.app))

### 1 · Configure the backend secret

```bash
# backend/.env
SUPERDOCS_API_KEY=sk_your_key_here
```

### 2 · Run the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# .\venv\Scripts\activate       # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server (hot-reload enabled)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be live at **`http://127.0.0.1:8000`**.  
Interactive API docs: **`http://127.0.0.1:8000/docs`**

### 3 · Run the frontend

```bash
cd frontend

npm install
npm run dev
```

The UI will be available at **`http://localhost:3000`**.
