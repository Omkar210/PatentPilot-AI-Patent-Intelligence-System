# Investigation & Implementation Strategy Report: Milestone 2 — Planner Agent (`agents/planner.py`)

## 1. Observation

Direct inspection of project files and configurations revealed the following key findings:

### 1.1 State Schema (`state.py`)
- `PatentPilotState` is a `TypedDict(total=False)` defined in `state.py`.
- **Input Key**: Stage 1 provides `user_query: str` ("The raw natural-language query submitted by the user.").
- **Output Key**: Stage 2 expects `search_keywords: List[str]` ("3-6 focused search keywords extracted from user_query.").
- Every node in the LangGraph pipeline must accept `PatentPilotState` and return a dictionary containing updated partial state keys.

### 1.2 Pipeline Integration (`graph.py`)
- Currently, `graph.py` contains a stub function:
  ```python
  def planner_agent_node(state: PatentPilotState) -> Dict[str, Any]:
      """Stage 2: Planner agent — breaks query into search keywords."""
      return {"search_keywords": state.get("search_keywords", [])}
  ```
- `graph.py` wires `START -> user_query -> planner -> search -> ...`.
- Implementation of `agents/planner.py` should expose `planner_agent_node(state: PatentPilotState) -> Dict[str, Any]`, which will replace or be imported into `graph.py`.

### 1.3 Environment Variables & LLM Stack (`.env.example` & `requirements.txt`)
- `.env.example` defines:
  - `GOOGLE_API_KEY=your-google-gemini-api-key-here` (Primary hosted LLM provider)
  - `GROQ_API_KEY=your-groq-api-key-here` (Secondary fallback hosted LLM provider)
- `requirements.txt` includes:
  - `google-generativeai==0.8.5`
  - `groq==0.31.0`
  - `python-dotenv==1.1.1`
- `AGENTS.md` explicitly mandates:
  - LLM calls must go through hosted APIs (Gemini or Groq), never locally-loaded heavy models.
  - Temperature set to `0` for deterministic keyword generation.

### 1.4 Baseline Fallback Patterns (`ingestion/patentsview.py` & `ingestion/semantic_scholar.py`)
- Existing ingestion modules handle API key absence, unconfigured environment variables, and network failures gracefully by falling back to robust local mock/rule-based procedures rather than failing.
- A similar pattern must be applied to `planner.py`.

---

## 2. Logic Chain

From the observations, the implementation strategy for `agents/planner.py` and `tests/test_planner.py` is structured as follows:

```
                  ┌─────────────────────────────────────┐
                  │    planner_agent_node(state)        │
                  │   Extract state.get("user_query")   │
                  └──────────────────┬──────────────────┘
                                     │
                        Is GOOGLE_API_KEY configured?
                                     │
                     ┌───────────────┴───────────────┐
                    YES                              NO
                     │                               │
            Call Gemini API                 Is GROQ_API_KEY configured?
          (gemini-2.5-flash)                         │
          temperature = 0.0                  ┌───────┴───────┐
                     │                      YES              NO
           Success & Valid JSON?             │               │
             ┌───────┴───────┐        Call Groq API          │
            YES              NO     (llama-3.3-70b)          │
             │               │     temperature = 0.0         │
             │         ┌─────┴───────────────┐               │
             │      Success & Valid JSON?    │               │
             │        ┌──────┴───────┐       │               │
             │       YES             NO      │               │
             │        │              └───────┴───────────────┤
             │        │                                      │
             ▼        ▼                                      ▼
       ┌──────────────────┐                     ┌──────────────────────────┐
       │ Parse JSON Output│                     │  Rule-Based Keyword      │
       │ Clean & Enforce  │                     │  Extractor (NLP/Regex)   │
       │  3-6 Keywords    │                     │  Enforce 3-6 Keywords    │
       └─────────┬────────┘                     └────────────┬─────────────┘
                 │                                           │
                 └─────────────────────┬─────────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │ Return {"search_keywords":    │
                       │          [kw1, kw2, ...]}     │
                       └───────────────────────────────┘
```

### 2.1 Component Specifications for `agents/planner.py`

#### A. Response Parser (`parse_keywords_json`)
- Sanitizes LLM output text by stripping markdown fence wrappers (e.g. ```json ... ``` or ``` ... ```).
- Uses `json.loads()` to parse JSON string.
- If JSON parsing fails, uses regex fallback `re.findall(r'"([^"]+)"', text)` to extract string literals.
- Filters out non-string items, empty strings, and duplicates (case-insensitive while retaining clean formatting).
- Returns list of keywords.

#### B. Primary LLM Provider: Google Gemini (`_call_gemini`)
- Checks `GOOGLE_API_KEY` (ignores default placeholder string).
- Configures `google.generativeai` with `GOOGLE_API_KEY`.
- Uses model `gemini-2.5-flash` (or `gemini-1.5-flash` fallback).
- Prompt specifies strict JSON array output format for 3–6 search keywords.
- Configures `temperature=0.0`.
- Catches all API / network exceptions safely and logs warnings.

#### C. Fallback LLM Provider: Groq (`_call_groq`)
- Checks `GROQ_API_KEY` (ignores default placeholder string).
- Instantiates `groq.Groq(api_key=...)`.
- Calls chat completion with model `llama-3.3-70b-versatile` (or `llama3-8b-8192`) and `temperature=0.0`.
- Catches API exceptions safely.

#### D. Rule-Based Fallback Extractor (`extract_keywords_rule_based`)
- Executed when both hosted APIs fail, API keys are missing/invalid, or parsing returns invalid keyword counts.
- Operations:
  1. Handles empty / whitespace queries by returning generic fallback list `["artificial intelligence", "patent intelligence", "prior art"]`.
  2. Cleans text: converts to lowercase, removes punctuation/symbols while preserving hyphens.
  3. Filters common English stop words and domain noise words (e.g., `a, an, the, for, in, of, system, method, device, invention, patent, prior, art, search, using`).
  4. Multi-word phrase extraction: identifies technical 2-3 word sequences (e.g., "vision transformer", "pedestrian detection", "deep learning", "autonomous vehicle").
  5. Single word extraction: collects distinct technical nouns/verbs if phrase count is below 3.
  6. Final keyword list size enforcement:
     - If count < 3: pads with query terms or domain defaults up to 3 keywords.
     - If count > 6: truncates to 6 keywords.

#### E. Node Handler (`planner_agent_node`)
- Function signature: `planner_agent_node(state: PatentPilotState) -> Dict[str, Any]`
- Gets `user_query` from `state.get("user_query", "")`.
- Sequentially tries: Gemini -> Groq -> Rule-based fallback.
- Validates that returned list strictly has 3 to 6 non-empty strings.
- Returns `{"search_keywords": keywords}`.

---

### 2.2 Test Design Specifications for `tests/test_planner.py`

The test suite will cover the following scenarios using `pytest` and `unittest.mock`:

1. **`test_planner_gemini_success`**:
   - Mock `google.generativeai.GenerativeModel.generate_content` returning `["deep learning", "vision transformer", "pedestrian detection"]`.
   - Verify `planner_agent_node` uses Gemini response and returns 3 valid keywords.

2. **`test_planner_gemini_markdown_codeblock_parsing`**:
   - Mock Gemini returning markdown codeblock: ` ```json\n["vision transformer", "object detection", "neural network", "lidar sensor"]\n``` `.
   - Verify parser strips codeblock delimiters and correctly extracts list of 4 keywords.

3. **`test_planner_groq_fallback_on_gemini_failure`**:
   - Mock Gemini throwing an `Exception` or return None (simulating API failure/rate limit).
   - Mock Groq API `Groq.chat.completions.create` returning JSON string `["autonomous vehicle", "sensor fusion", "path planning"]`.
   - Verify Groq fallback succeeds and keywords are returned.

4. **`test_planner_rule_based_fallback_no_api_keys`**:
   - Mock environment variables `GOOGLE_API_KEY` and `GROQ_API_KEY` to `None` or placeholder strings.
   - Input query: `"System and method for autonomous vehicle navigation using vision transformers and lidar sensors"`.
   - Verify rule-based keyword extractor returns 3–6 extracted technical keywords (e.g. `['autonomous vehicle navigation', 'vision transformers', 'lidar sensors']`).

5. **`test_planner_empty_user_query`**:
   - Input state `{"user_query": ""}`.
   - Verify fallback logic handles empty input gracefully without raising exceptions, returning 3 default keywords.

6. **`test_planner_keyword_count_clamping`**:
   - Test LLM responses with <3 or >6 keywords.
   - Verify output is clamped/padded to guarantee $3 \le \text{len(search\_keywords)} \le 6$.

7. **`test_planner_state_dict_interface`**:
   - Call `planner_agent_node` with partial `PatentPilotState`.
   - Assert return value is a `dict` containing `"search_keywords"` with type `List[str]`.

---

## 3. Caveats

1. **SDK Availability**:
   - If `google-generativeai` or `groq` packages are uninstalled in a specific execution environment, imports should be wrapped in `try-except ImportError` so the module falls back gracefully to rule-based processing rather than throwing `ImportError` on load.
2. **Model Name Availability**:
   - Hosted API endpoints may occasionally update model aliases (e.g., `gemini-2.5-flash` vs `gemini-1.5-flash`, `llama-3.3-70b-versatile` vs `llama3-8b-8192`). The implementation should use primary recommended model names with fallback to standard aliases.
3. **JSON Extraction Diversity**:
   - LLMs can return JSON wrapped in backticks, nested JSON objects `{"keywords": [...]}` or plain text lists. Robust parsing is essential to prevent falling back unnecessarily when valid JSON is returned in slightly variant formats.

---

## 4. Conclusion

- Requirement R2 Planner Agent (`agents/planner.py`) should be implemented as a modular agent with a multi-tier fallback architecture: **Gemini (primary) -> Groq (secondary) -> Rule-based NLP Extractor (tertiary)**.
- Interface contract `planner_agent_node(state: PatentPilotState) -> Dict[str, Any]` strictly returns `{"search_keywords": List[str]}` containing 3 to 6 keywords.
- Complete test suite `tests/test_planner.py` will guarantee resilience, full fallback coverage, parsing flexibility, and state interface compliance.

---

## 5. Verification Method

To verify the design and implementation when `agents/planner.py` and `tests/test_planner.py` are written:

1. **Run Unit Tests**:
   ```bash
   pytest tests/test_planner.py -v
   ```
2. **Run Pipeline Integration Check**:
   ```bash
   python graph.py
   ```
3. **Verify State Shape**:
   - Ensure output of `planner_agent_node` contains key `"search_keywords"`.
   - Ensure `isinstance(result["search_keywords"], list)` is `True` and $3 \le \text{len}(result["search_keywords"]) \le 6$.
