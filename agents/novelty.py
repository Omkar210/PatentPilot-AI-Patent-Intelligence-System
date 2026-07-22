"""
agents/novelty.py — Stage 9: Novelty Assessment Agent Node

Evaluates the novelty of the user's invention against flagged prior_art
using Google Gemini 2.5 Flash / Groq SDK (temperature 0.2).
Requires structured JSON output with novelty_score (0-100) and an explainable
novelty_explanation citing specific prior art overlaps.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from state import PatentPilotState

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY and GOOGLE_API_KEY != "your-google-gemini-api-key-here":
    genai.configure(api_key=GOOGLE_API_KEY)


def _rule_based_novelty_fallback(user_query: str, prior_art: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generates a structured novelty score & explanation when LLM API is unavailable."""
    count = len(prior_art)
    if count == 0:
        score = 85
        explanation = f"High Novelty (Score: 85/100). No direct prior art documents were found exceeding the similarity threshold of 0.75 for query: '{user_query}'."
    elif count == 1:
        art_id = prior_art[0].get("source_id", "Prior Art 1")
        sim = prior_art[0].get("similarity", 0.75)
        score = 65
        explanation = f"Moderate Novelty (Score: 65/100). Found 1 closely related prior art document ({art_id}, similarity {sim}) overlapping with the technical description. Specific technical claim distinctions must be emphasized during filing."
    else:
        art_ids = [str(a.get("source_id")) for a in prior_art[:3]]
        score = max(25, 60 - (count * 10))
        explanation = f"Lower Novelty (Score: {score}/100). Found {count} overlapping prior art references ({', '.join(art_ids)}). Significant overlap detected in core concepts. Detailed claim differentiation and narrow technical limitation additions are required."

    return {
        "novelty_score": score,
        "novelty_explanation": explanation
    }


def novelty_assessment_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Novelty Assessment Node accepting and returning partial PatentPilotState.
    """
    user_query = str(state.get("user_query") or "").strip()
    prior_art = state.get("prior_art") or []

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your-google-gemini-api-key-here":
        return _rule_based_novelty_fallback(user_query, prior_art)

    # Format prior art list for LLM prompt
    art_context = ""
    if prior_art:
        for idx, art in enumerate(prior_art, start=1):
            art_context += f"--- Prior Art {idx} (ID: {art.get('source_id')}, Similarity: {art.get('similarity')}) ---\n"
            art_context += f"Title: {art.get('title')}\n"
            art_context += f"Snippet: {art.get('text_snippet')}\n\n"
    else:
        art_context = "No prior art documents exceeded the similarity threshold of 0.75.\n"

    prompt = f"""You are a Patent Examiner and Patent Novelty Evaluation Agent.

Evaluate the novelty of the user's invention query against the provided prior art documents.

User Invention Query:
\"{user_query}\"

Prior Art References Found:
{art_context}

Provide a structured JSON response with exact keys:
{{
  "novelty_score": <integer from 0 to 100, where 100 is completely novel and 0 is entirely anticipated>,
  "novelty_explanation": "<detailed, professional 2-3 paragraph explanation citing specific prior art IDs and technical overlap or distinctions>"
}}
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
        )
        if response and response.text:
            parsed = json.loads(response.text)
            score = int(parsed.get("novelty_score", 50))
            score = max(0, min(100, score))
            explanation = str(parsed.get("novelty_explanation", ""))
            return {
                "novelty_score": score,
                "novelty_explanation": explanation
            }
    except Exception as e:
        logger.warning(f"Gemini API Novelty Assessment failed: {e}. Using fallback.")

    return _rule_based_novelty_fallback(user_query, prior_art)
