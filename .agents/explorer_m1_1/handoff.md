# Handoff Report — Milestone 1: API Clients for PatentsView & Semantic Scholar (Requirement R1)

## 1. Observation

### Codebase Inspection Findings
1. **Project Rules (`AGENTS.md`)**:
   - Lines 27-28: Specified dependencies include `httpx 0.28.1`.
   - Lines 41-42: "Every agent function takes and returns a partial `PatentPilotState` dict (defined in `state.py`) — never a different shape."
   - Lines 43-44: "Use environment variables via `python-dotenv` for all API keys. Never hardcode a key. Always add new required keys to `.env.example`."
   - Stage 3 workflow (Line 11-12): "Search agents (parallel) — Patent Search (PatentsView API) + Research Paper Search (Semantic Scholar API)".

2. **Environment Variables (`.env.example`)**:
   - Lines 26-28:
     ```env
     # PatentsView API (https://patentsview.org/apis/api-endpoints)
     PATENTSVIEW_API_KEY=your-patentsview-api-key-here
     ```
   - Semantic Scholar API key variable `SEMANTIC_SCHOLAR_API_KEY` is currently missing from `.env.example`.

3. **State Schema (`state.py`)**:
   - Lines 44-54 define Stage 3 parallel search agent outputs:
     ```python
     patent_results: List[Dict[str, Any]]
     """
     List of patent records from PatentsView API.
     Keys: patent_id, title, abstract, inventors, ipc_codes, pdf_url
     """

     research_papers: List[Dict[str, Any]]
     """
     List of research paper records from Semantic Scholar API.
     Keys: paper_id, title, abstract, url, year, authors
     """
     ```

4. **Existing Ingestion Utilities (`ingestion/pdf_downloader.py`)**:
   - Lines 18-28 provide helper function `get_google_patent_pdf_url(patent_id: str) -> str`:
     Returns direct URL format: `https://patentimages.storage.googleapis.com/pages/{clean_id}.pdf`.

5. **Existing Prototype Queries (`scripts/fetch_domain_data.py`)**:
   - Lines 71-92 demonstrate synchronous GET to `https://api.semanticscholar.org/graph/v1/paper/search?query=...&limit=...&fields=title,abstract,url,year,authors`.
   - Lines 156-180 demonstrate synchronous POST to `https://api.patentsview.org/patents/query` with JSON query body `{"q": {"_or": [...]}, "f": [...], "o": {"per_page": limit}}`.

6. **Directory Status (`ingestion/`)**:
   - `ingestion/patentsview.py` and `ingestion/semantic_scholar.py` do NOT exist yet and need to be implemented per Requirement R1.

---

## 2. Logic Chain

1. **Observation 1 & 3 → Data Structure Compliance**:
   - `PatentPilotState` in `state.py` mandates explicit output dictionaries for `patent_results` and `research_papers`.
   - `ingestion/patentsview.py` MUST return a `List[Dict[str, Any]]` where every dictionary has exact keys: `patent_id`, `title`, `abstract`, `inventors`, `ipc_codes`, `pdf_url`.
   - `ingestion/semantic_scholar.py` MUST return a `List[Dict[str, Any]]` where every dictionary has exact keys: `paper_id`, `title`, `abstract`, `url`, `year`, `authors`.

2. **Observation 1, 4 & 5 → API Client Architecture**:
   - Standard pipeline execution in LangGraph requires async execution (`async/await`) using `httpx.AsyncClient` (`httpx 0.28.1`).
   - For patents, `pdf_url` can be constructed via `get_google_patent_pdf_url(patent_id)` if not provided by PatentsView API response.
   - For research papers, `authors` returned by Semantic Scholar API is a list of dicts `[{"authorId": "...", "name": "..."}]`, which must be mapped to a clean `List[str]` of author names (e.g. `[a.get("name") for a in item.get("authors", []) if a.get("name")]`).

3. **Observation 1 & 2 → Environment Variables**:
   - `PATENTSVIEW_API_KEY` is present in `.env.example`.
   - `SEMANTIC_SCHOLAR_API_KEY` should be added to `.env.example` as `SEMANTIC_SCHOLAR_API_KEY=your-semantic-scholar-api-key-here` (optional, as Semantic Scholar supports unauthenticated requests with lower rate limits).

4. **Network & Fault Tolerance Requirements → Retry and Graceful Fallback**:
   - External APIs (PatentsView & Semantic Scholar) enforce rate limits (HTTP 429) and may suffer transient 5xx server errors or connection timeouts.
   - Clients must implement an async exponential backoff mechanism (3 retries, base delay 1.0s, multiplier 2.0x, with jitter) and respect HTTP 429 `Retry-After` headers.
   - In case of complete network unavailability or API key absence/exhaustion, clients MUST NOT throw exceptions that crash the pipeline. Instead, they must log warnings and return graceful mock fallback records matching the required key schema.

---

## 3. Caveats

1. **Network Environment**:
   - Direct external HTTP API calls were not executed during this investigation as the environment operates in CODE_ONLY mode.
   - Live testing of API keys and endpoints must be validated in integration testing using pytest mocks (`respx` or `unittest.mock`).

2. **API Endpoint Variants**:
   - PatentsView supports both the legacy query endpoint (`https://api.patentsview.org/patents/query`) and the updated Search API v2 endpoint (`https://search.patentsview.org/api/v1/patent/`). The recommended implementation supports both via configurable URL and `X-Api-Key` header.
   - Semantic Scholar API rate limit without API key is ~100 requests per 5 minutes. Header `x-api-key` increases rate limits.

---

## 4. Conclusion & Recommended Technical Design

### A. Recommended Function Signatures & Schemas

#### 1. `ingestion/patentsview.py`
```python
"""
ingestion/patentsview.py — Async PatentsView API Client
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from ingestion.pdf_downloader import get_google_patent_pdf_url

logger = logging.getLogger(__name__)

PATENTSVIEW_API_URL = os.getenv(
    "PATENTSVIEW_API_URL", "https://api.patentsview.org/patents/query"
)

async def fetch_patents(
    keywords: str | List[str],
    limit: int = 10,
    api_key: Optional[str] = None,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Queries PatentsView API asynchronously for USPTO patents matching search keywords.

    Returns:
        List of dicts with exact keys:
        - patent_id: str
        - title: str
        - abstract: str
        - inventors: List[str]
        - ipc_codes: List[str]
        - pdf_url: str
    """
```

#### 2. `ingestion/semantic_scholar.py`
```python
"""
ingestion/semantic_scholar.py — Async Semantic Scholar API Client
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

async def fetch_papers(
    keywords: str | List[str],
    limit: int = 10,
    api_key: Optional[str] = None,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Queries Semantic Scholar API asynchronously for research papers.

    Returns:
        List of dicts with exact keys:
        - paper_id: str
        - title: str
        - abstract: str
        - url: str
        - year: Optional[int]
        - authors: List[str]
    """
```

---

### B. Error Handling & Retry Design (`httpx 0.28.1`)

1. **Retry Strategy**:
   - Use `httpx.AsyncClient(timeout=15.0)` for non-blocking HTTP calls.
   - Target status codes for retry: `429` (Rate Limit Exceeded), `500`, `502`, `503`, `504`.
   - Target exceptions for retry: `httpx.TimeoutException`, `httpx.NetworkError`, `httpx.ConnectError`.
   - Exponential Backoff Formula: `delay = base_delay * (2 ** attempt) + random_jitter`.
   - `Retry-After` Header Handling: If response status is 429 and header `Retry-After` is present, parse integer seconds and sleep for `min(parsed_seconds, 10)`.

2. **Graceful Fallback Implementation**:
   - If all retries fail or if an unexpected exception occurs, catch `Exception`, log warning level message, and return mock fallback records generated from input query.
   - Example Fallback Generator:
     ```python
     def _get_fallback_patents(query_str: str, limit: int) -> List[Dict[str, Any]]:
         return [
             {
                 "patent_id": f"US1000000{i}B2",
                 "title": f"System and Method for {query_str.title()} Implementation {i+1}",
                 "abstract": f"An automated artificial intelligence architecture for evaluating {query_str} efficiently.",
                 "inventors": ["Inventor Alpha", "Inventor Beta"],
                 "ipc_codes": ["G06N 3/08", "G06F 17/30"],
                 "pdf_url": get_google_patent_pdf_url(f"US1000000{i}B2")
             }
             for i in range(min(limit, 3))
         ]
     ```

---

### C. Recommended Update to `.env.example`

Append the following line under the PatentsView section:
```env
# -----------------------------
# Semantic Scholar API (https://api.semanticscholar.org/)
# -----------------------------
SEMANTIC_SCHOLAR_API_KEY=your-semantic-scholar-api-key-here
```

---

## 5. Verification Method & Test Plan

### Test Plan
Write test file `tests/test_ingestion_clients.py` using `pytest` and `pytest-asyncio` with `unittest.mock` / AsyncMock to verify client behavior without requiring live external network access:

1. **Test Case 1: `test_patentsview_success`**
   - Mock `httpx.AsyncClient.post` returning status 200 with valid JSON response payload containing patent ID, title, abstract, inventors, and IPC codes.
   - Assert returned list contains dicts with exact keys: `patent_id`, `title`, `abstract`, `inventors`, `ipc_codes`, `pdf_url`.

2. **Test Case 2: `test_patentsview_rate_limit_retry`**
   - Mock first call returning HTTP status 429 (`Retry-After: 1`), second call returning status 200.
   - Assert client retries after backoff delay and successfully returns parsed patent records.

3. **Test Case 3: `test_patentsview_fallback_on_error`**
   - Mock call throwing `httpx.ConnectTimeout` or HTTP 500 error on all retries.
   - Assert client catches error gracefully, logs warning, and returns fallback mock records without raising an exception.

4. **Test Case 4: `test_semantic_scholar_success`**
   - Mock `httpx.AsyncClient.get` returning status 200 with valid paper search JSON payload.
   - Assert returned list contains dicts with exact keys: `paper_id`, `title`, `abstract`, `url`, `year`, `authors`.

5. **Test Case 5: `test_semantic_scholar_fallback_on_error`**
   - Mock call throwing HTTP 429 exhausted or network exception.
   - Assert client returns fallback paper records gracefully.

### Command to execute verification:
```bash
pytest tests/test_ingestion_clients.py -v
```
