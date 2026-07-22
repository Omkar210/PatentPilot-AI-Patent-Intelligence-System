"""
agents/planner.py — Stage 2: Planner Agent

Extracts 3 to 6 focused, relevant search keywords/phrases from a user's natural language query.
Uses a multi-tier execution strategy:
1. Primary LLM: Google Gemini (gemini-2.5-flash / gemini-1.5-flash, temperature=0.0)
2. Fallback LLM: Groq (llama-3.3-70b-versatile / llama3-8b-8192, temperature=0.0)
3. Fallback NLP: Rule-based phrase & keyword extractor

Guarantees output returned is a dictionary {"search_keywords": List[str]} containing 3-6 strings.
"""

import os
import re
import json
import logging
from typing import Any, Dict, List, Optional

from state import PatentPilotState

logger = logging.getLogger(__name__)

# Standard domain fallback keywords when query provides insufficient tokens
DEFAULT_FALLBACK_KEYWORDS = [
    "artificial intelligence",
    "patent intelligence",
    "prior art",
]

# Stop words to filter out during rule-based keyword extraction
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # Patent / generic domain noise words
    "system", "method", "apparatus", "device", "invention", "patent", "prior",
    "art", "search", "using", "used", "based", "novel", "new", "improved", "process",
    "relates", "disclosed", "comprising", "includes", "feature", "features", "claim",
    "claims", "description"
}


def _is_valid_api_key(key: Optional[str]) -> bool:
    """Checks if an API key is present, non-empty, and not a placeholder."""
    if not key or not isinstance(key, str):
        return False
    k = key.strip()
    if not k:
        return False
    lower_k = k.lower()
    if lower_k.startswith("your-") or lower_k.startswith("your_") or "placeholder" in lower_k:
        return False
    return True


def parse_keywords_json(text: str) -> List[str]:
    """
    Parses LLM output into a list of cleaned keyword strings.
    Handles raw JSON arrays, JSON wrapped in markdown codeblocks (```json ... ```),
    JSON objects with keyword keys, or regex fallback.
    """
    if not text or not isinstance(text, str):
        return []

    cleaned = text.strip()

    # Stripping markdown codeblock wrapper if present
    codeblock_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(codeblock_pattern, cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    keywords: List[str] = []

    # Attempt 1: Standard JSON decoding
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            keywords = [str(item).strip() for item in data if item and str(item).strip()]
        elif isinstance(data, dict):
            # Look for common key names
            for key in ["search_keywords", "keywords", "terms", "queries", "items"]:
                if key in data and isinstance(data[key], list):
                    keywords = [str(item).strip() for item in data[key] if item and str(item).strip()]
                    break
            if not keywords:
                # Pick first list value in dict if any
                for val in data.values():
                    if isinstance(val, list):
                        keywords = [str(item).strip() for item in val if item and str(item).strip()]
                        if keywords:
                            break
    except (json.JSONDecodeError, TypeError):
        pass

    # Attempt 2: Regex extraction for quoted strings if JSON parse failed or returned empty
    if not keywords:
        quoted_items = re.findall(r'"([^"]+)"', cleaned)
        if quoted_items:
            keywords = [item.strip() for item in quoted_items if item.strip()]

    # Attempt 3: Line-by-line fallback if it looks like a bullet/numbered list
    if not keywords and ("\n" in cleaned or "-" in cleaned or "*" in cleaned):
        lines = cleaned.splitlines()
        for line in lines:
            line_cleaned = re.sub(r"^[\s*\-\d\.]+", "", line).strip()
            if line_cleaned:
                keywords.append(line_cleaned)

    # Deduplicate while preserving order and casing (using lowercase key for uniqueness)
    seen = set()
    deduped: List[str] = []
    for kw in keywords:
        kw_clean = kw.strip().strip('",\'')
        if kw_clean:
            lower_kw = kw_clean.lower()
            if lower_kw not in seen:
                seen.add(lower_kw)
                deduped.append(kw_clean)

    return deduped


def extract_keywords_rule_based(user_query: str) -> List[str]:
    """
    NLP / phrase-extraction fallback when LLMs are unavailable or fail.
    Extracts multi-word technical phrases and key terms from user_query.
    """
    if not user_query or not user_query.strip():
        return list(DEFAULT_FALLBACK_KEYWORDS)

    # Normalize text
    text = user_query.strip().lower()
    # Replace non-alphanumeric chars (except hyphens) with space
    clean_text = re.sub(r"[^\w\s\-]", " ", text)
    words = [w.strip() for w in clean_text.split() if w.strip()]

    if not words:
        return list(DEFAULT_FALLBACK_KEYWORDS)

    # Filtered tokens (non-stopwords and length > 1)
    filtered_tokens = [w for w in words if w not in STOP_WORDS and len(w) > 1]

    extracted: List[str] = []

    # 1. Multi-word phrases (bigrams and trigrams from adjacent non-stopwords in original sentence)
    phrases: List[str] = []
    i = 0
    while i < len(words):
        if words[i] not in STOP_WORDS and len(words[i]) > 1:
            start = i
            end = i
            while end < len(words) and words[end] not in STOP_WORDS and len(words[end]) > 1:
                end += 1
            span = words[start:end]
            if len(span) >= 2:
                phrase = " ".join(span)
                if phrase not in phrases:
                    phrases.append(phrase)
            i = end
        else:
            i += 1

    extracted.extend(phrases)

    # 2. Add individual filtered tokens if phrases are few
    for token in filtered_tokens:
        if token not in extracted:
            extracted.append(token)

    return clamp_keywords(extracted, user_query)


def clamp_keywords(keywords: List[str], user_query: str) -> List[str]:
    """
    Guarantees returned keywords list contains strictly between 3 and 6 non-empty strings.
    Pads with rule-based phrase extraction or default fallbacks if < 3.
    Truncates to 6 if > 6.
    """
    valid_kws: List[str] = []
    seen = set()

    for kw in keywords:
        if kw and isinstance(kw, str):
            cleaned = kw.strip().strip('",\'')
            if cleaned:
                lower = cleaned.lower()
                if lower not in seen:
                    seen.add(lower)
                    valid_kws.append(cleaned)

    # Pad if < 3
    if len(valid_kws) < 3:
        # Try extracting additional terms from user query via rule-based
        rule_extracted = extract_keywords_rule_based(user_query) if user_query and user_query.strip() else []
        for rkw in rule_extracted:
            r_lower = rkw.lower()
            if r_lower not in seen:
                seen.add(r_lower)
                valid_kws.append(rkw)
            if len(valid_kws) >= 3:
                break

    # Pad with default fallbacks if still < 3
    if len(valid_kws) < 3:
        for fkw in DEFAULT_FALLBACK_KEYWORDS:
            f_lower = fkw.lower()
            if f_lower not in seen:
                seen.add(f_lower)
                valid_kws.append(fkw)
            if len(valid_kws) >= 3:
                break

    # Truncate if > 6
    if len(valid_kws) > 6:
        valid_kws = valid_kws[:6]

    return valid_kws


def _call_gemini(user_query: str) -> Optional[List[str]]:
    """
    Primary LLM Execution: Google Gemini (gemini-2.5-flash / gemini-1.5-flash).
    Returns list of keywords if successful, else None.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not _is_valid_api_key(api_key):
        logger.info("Gemini API key not configured or is default placeholder.")
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai package not installed.")
        return None

    prompt = (
        "You are a patent search planner. Extract 3 to 6 concise, highly targeted patent search keywords or technical phrases "
        "from the user query. Focus on core algorithms, systems, components, and methodologies.\n"
        "Return ONLY a JSON array of 3 to 6 strings, with no markdown wrappers or additional text.\n"
        "Example output: [\"vision transformer\", \"object detection\", \"autonomous vehicle\"]\n\n"
        f"User Query: {user_query}"
    )

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    try:
        genai.configure(api_key=api_key)
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.0}
                )
                if response and hasattr(response, "text") and response.text:
                    parsed = parse_keywords_json(response.text)
                    if parsed:
                        logger.info(f"Gemini ({model_name}) successfully extracted keywords.")
                        return parsed
            except Exception as e:
                logger.warning(f"Gemini model {model_name} failed: {e}")
                continue
    except Exception as e:
        logger.warning(f"Gemini API execution failed: {e}")

    return None


def _call_groq(user_query: str) -> Optional[List[str]]:
    """
    Secondary Fallback LLM Execution: Groq (llama-3.3-70b-versatile / llama3-8b-8192).
    Returns list of keywords if successful, else None.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not _is_valid_api_key(api_key):
        logger.info("Groq API key not configured or is default placeholder.")
        return None

    try:
        from groq import Groq
    except ImportError:
        logger.warning("groq package not installed.")
        return None

    prompt = (
        "You are a patent search planner. Extract 3 to 6 concise, highly targeted patent search keywords or technical phrases "
        "from the user query. Focus on core algorithms, systems, components, and methodologies.\n"
        "Return ONLY a JSON array of 3 to 6 strings, with no markdown wrappers or additional text.\n"
        "Example output: [\"vision transformer\", \"object detection\", \"autonomous vehicle\"]\n\n"
        f"User Query: {user_query}"
    )

    models_to_try = ["llama-3.3-70b-versatile", "llama3-8b-8192"]

    try:
        client = Groq(api_key=api_key)
        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                )
                if response and response.choices and response.choices[0].message.content:
                    content = response.choices[0].message.content
                    parsed = parse_keywords_json(content)
                    if parsed:
                        logger.info(f"Groq ({model_name}) successfully extracted keywords.")
                        return parsed
            except Exception as e:
                logger.warning(f"Groq model {model_name} failed: {e}")
                continue
    except Exception as e:
        logger.warning(f"Groq API execution failed: {e}")

    return None


def planner_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Stage 2: Planner agent node function for LangGraph pipeline.

    Reads state['user_query'] and returns updated state dict:
    {"search_keywords": List[str]} containing strictly 3 to 6 keywords.
    """
    user_query = state.get("user_query", "") if state else ""
    if not isinstance(user_query, str):
        user_query = str(user_query) if user_query is not None else ""

    # If query is empty or whitespace-only, return clamped fallback directly
    if not user_query.strip():
        keywords = clamp_keywords([], user_query)
        return {"search_keywords": keywords}

    # 1. Try Gemini (Primary hosted LLM)
    gemini_result = _call_gemini(user_query)
    if gemini_result:
        keywords = clamp_keywords(gemini_result, user_query)
        return {"search_keywords": keywords}

    # 2. Try Groq (Secondary fallback hosted LLM)
    groq_result = _call_groq(user_query)
    if groq_result:
        keywords = clamp_keywords(groq_result, user_query)
        return {"search_keywords": keywords}

    # 3. Rule-based NLP extraction (Tertiary offline fallback)
    logger.info("Falling back to rule-based keyword extraction.")
    keywords = extract_keywords_rule_based(user_query)
    keywords = clamp_keywords(keywords, user_query)

    return {"search_keywords": keywords}
