# Forensic Audit Report — Milestone 2 (Planner Agent)

## 1. Observation

### Static Analysis of Implementation (`agents/planner.py`)
- **Primary LLM Execution (`_call_gemini`, lines 231–278)**: Genuine integration using `google.generativeai` targeting `gemini-2.5-flash` and `gemini-1.5-flash` with zero temperature. Checks `GOOGLE_API_KEY` validity via `_is_valid_api_key` (lines 53–63).
- **Secondary LLM Execution (`_call_groq`, lines 280–329)**: Genuine fallback integration using `groq.Groq` targeting `llama-3.3-70b-versatile` and `llama3-8b-8192` with zero temperature.
- **Rule-Based NLP Phrase Extractor (`extract_keywords_rule_based`, lines 134–181)**: Genuine NLP logic extracting multi-word bigrams/trigrams and key unigrams filtered against a domain stopword set (`STOP_WORDS`, lines 31–50).
- **JSON & Markdown Parser (`parse_keywords_json`, lines 66–131)**: Parses raw JSON arrays, markdown wrapped blocks (`` ```json ... ``` ``), JSON objects with keyword keys, regex-quoted strings, and bullet lists.
- **Keyword Clamping (`clamp_keywords`, lines 184–228)**: Enforces boundary condition that returned keyword list contains between 3 and 6 strings.
- **LangGraph State Compliance (`planner_agent_node`, lines 332–366)**: Accepts `PatentPilotState` and returns `{"search_keywords": List[str]}` matching schema.

### Empirical Keyword Extraction Verification
Ran rule-based keyword extraction on novel domain inputs (Command: `$env:PYTHONPATH="."; .\venv\Scripts\python.exe -c "..."`):
- Input: `"Method for CRISPR Cas9 genomic gene editing in human stem cells"`
  Output: `['crispr cas9 genomic gene editing', 'human stem cells', 'crispr', 'cas9', 'genomic', 'gene']`
- Input: `"Quantum key distribution using polarized photon quantum states"`
  Output: `['quantum key distribution', 'polarized photon quantum states', 'quantum', 'key', 'distribution', 'polarized']`
- Input: `"Solid state lithium ion battery electrolyte separator matrix"`
  Output: `['solid state lithium ion battery electrolyte separator matrix', 'solid', 'state', 'lithium', 'ion', 'battery']`

### Unit Test Execution (`tests/test_planner.py`)
Ran unit test suite via virtualenv pytest:
`$env:PYTHONPATH="."; .\venv\Scripts\pytest.exe tests/test_planner.py -v`
Result:
```
tests/test_planner.py::test_is_valid_api_key PASSED                      [ 11%]
tests/test_planner.py::test_parse_keywords_json_formats PASSED           [ 22%]
tests/test_planner.py::test_planner_gemini_success PASSED                [ 33%]
tests/test_planner.py::test_planner_markdown_codeblock_stripping PASSED  [ 44%]
tests/test_planner.py::test_planner_groq_fallback_when_gemini_fails PASSED [ 55%]
tests/test_planner.py::test_planner_rule_based_fallback_no_api_keys PASSED [ 66%]
tests/test_planner.py::test_planner_empty_user_query PASSED              [ 77%]
tests/test_planner.py::test_planner_keyword_count_boundary_clamping PASSED [ 88%]
tests/test_planner.py::test_planner_state_dict_return_schema PASSED      [100%]

9 passed in 0.04s
```

### LangGraph Integration Verification (`graph.py`)
Ran full graph execution script:
`$env:PYTHONPATH="."; .\venv\Scripts\python.exe graph.py`
Result: Successful execution; state updated with `search_keywords: ['test query', 'test', 'query', 'intelligence']`.

### Stress Testing & Failure Mode Discovery (`.agents/auditor_m2/test_stress.py`)
Stress testing revealed a **mutual recursion bug** between `extract_keywords_rule_based` and `clamp_keywords`:
- `agents/planner.py:181`: `extract_keywords_rule_based` calls `clamp_keywords(extracted, user_query)`.
- `agents/planner.py:205`: `clamp_keywords` calls `extract_keywords_rule_based(user_query)` when `len(valid_kws) < 3`.
- When `user_query` is non-empty but contains only punctuation (e.g., `"!@#$%^&*()"`) or only stopwords (e.g., `"the a an"`), `extract_keywords_rule_based` produces 0 extracted keywords and calls `clamp_keywords`. `clamp_keywords` sees `< 3` keywords and re-invokes `extract_keywords_rule_based`, creating an infinite recursion loop:
  `RecursionError: maximum recursion depth exceeded`.

---

## 2. Logic Chain

1. **Static Analysis -> Genuine Logic**:
   - `agents/planner.py` does not contain hardcoded test results, facade implementations (`return ["const"]`), or pre-populated attestation artifacts.
   - LLM calls to Gemini and Groq are authentic SDK integrations with zero-temperature generation and key validation.
   - Rule-based extraction dynamically parses bigrams and unigrams from input queries.
2. **Empirical Behavior -> Dynamic Output**:
   - Dynamic keyword extraction was verified across distinct technical fields (CRISPR, Quantum Cryptography, Battery Chemistry). Outputs matched query context, proving no fixed/canned response lists are returned.
3. **Execution & Compliance -> Tests & Graph Pass**:
   - All 9 unit tests pass under `pytest`.
   - `graph.py` imports and executes `planner_agent_node` correctly within the 11-stage LangGraph workflow.
4. **Stress Testing Flaw Assessment**:
   - The discovered `RecursionError` is an algorithmic recursion bug on edge-case inputs (queries with zero non-stopwords), not a deceptive attempt or integrity violation (no cheating or hardcoding was introduced).

---

## 3. Caveats

- **API Key Live Execution**: Live network calls to Gemini/Groq APIs were tested via unit test mocks. Real API execution relies on standard Google/Groq client libraries and valid API keys in `.env`.
- **Recursion Bug Recommendation**: `clamp_keywords` line 205 should avoid re-invoking `extract_keywords_rule_based` if it was called from `extract_keywords_rule_based`, or fallback directly to `DEFAULT_FALLBACK_KEYWORDS` when rule-extracted keywords are fewer than 3.

---

## 4. Conclusion

The Milestone 2 (Planner Agent) implementation is **authentic, genuine, and free of integrity violations** (no hardcoded test outputs, no facade implementations, no self-certifying dummy tests). All unit tests pass and LangGraph integration is complete.

**VERDICT: CLEAN**

---

## 5. Verification Method

To independently verify this audit:

1. **Run Unit Tests**:
   ```powershell
   $env:PYTHONPATH="."
   .\venv\Scripts\pytest.exe tests/test_planner.py -v
   ```
   *Expected*: 9 tests pass.

2. **Verify Dynamic Keyword Extraction**:
   ```powershell
   $env:PYTHONPATH="."
   .\venv\Scripts\python.exe -c "from agents.planner import extract_keywords_rule_based; print(extract_keywords_rule_based('CRISPR Cas9 gene editing'))"
   ```
   *Expected*: Keywords extracted dynamically matching query terms.

3. **Verify LangGraph Integration**:
   ```powershell
   $env:PYTHONPATH="."
   .\venv\Scripts\python.exe graph.py
   ```
   *Expected*: "Graph execution successful!" with `search_keywords` in state output.

4. **Reproduce Recursion Edge-Case Bug**:
   ```powershell
   $env:PYTHONPATH="."
   .\venv\Scripts\python.exe -c "from agents.planner import planner_agent_node; planner_agent_node({'user_query': 'the a an'})"
   ```
   *Expected*: `RecursionError: maximum recursion depth exceeded`.
