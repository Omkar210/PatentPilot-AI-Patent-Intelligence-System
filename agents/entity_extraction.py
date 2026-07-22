"""
agents/entity_extraction.py — Stage 5: Entity Extraction Agent Node

Extracts structured technical entities (algorithms, datasets, frameworks,
inventors, ipc_codes, keywords) from raw_documents using Google Gemini 2.5 Flash / Groq SDK.
Truncates input text to 3000 characters per document call to control cost/latency.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List
import google.generativeai as genai
from dotenv import load_dotenv
from state import PatentPilotState

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY and GOOGLE_API_KEY != "your-google-gemini-api-key-here":
    genai.configure(api_key=GOOGLE_API_KEY)


def _extract_entities_fallback(text: str, source_id: str) -> Dict[str, Any]:
    """Rule-based NLP fallback when LLM API key is absent or unavailable."""
    algos = re.findall(r"\b(?:neural network|transformer|cnn|rnn|lstm|resnet|bert|gpt|diffusion|svm|kmeans|random forest|attention mechanism)\b", text, re.I)
    datasets = re.findall(r"\b(?:imagenet|coco|squad|common crawl|mnist|cifar|kitti)\b", text, re.I)
    frameworks = re.findall(r"\b(?:pytorch|tensorflow|keras|jax|onnx|langchain|chromadb|neo4j)\b", text, re.I)
    
    return {
        "source_id": source_id,
        "algorithms": list(dict.fromkeys([a.title() for a in algos])),
        "datasets": list(dict.fromkeys([d.upper() for d in datasets])),
        "frameworks": list(dict.fromkeys([f.title() for f in frameworks])),
        "inventors": [],
        "ipc_codes": [],
        "keywords": list(dict.fromkeys([w.strip().lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", text[:500]) if w.lower() not in {"this", "that", "with", "from", "have", "been", "which"}]))[:8]
    }


def extract_entities_from_doc(doc_item: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts technical entities from a single document record."""
    source_id = str(doc_item.get("source_id") or doc_item.get("patent_id") or "").strip()
    text = str(doc_item.get("text") or doc_item.get("abstract") or "").strip()
    
    if not text:
        return _extract_entities_fallback("", source_id)

    # Truncate text to 3000 characters to control cost & latency
    truncated_text = text[:3000]

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your-google-gemini-api-key-here":
        return _extract_entities_fallback(truncated_text, source_id)

    prompt = f"""You are an expert patent AI entity extractor. Extract technical entities from the following patent/research document text.

Return ONLY a valid JSON object with these exact keys:
{{
  "source_id": "{source_id}",
  "algorithms": ["list of AI/ML/hardware algorithms or techniques mentioned"],
  "datasets": ["list of datasets or benchmarks mentioned"],
  "frameworks": ["list of software frameworks or libraries mentioned"],
  "inventors": ["list of inventors or authors mentioned"],
  "ipc_codes": ["list of IPC/CPC classification codes mentioned"],
  "keywords": ["list of 5-8 technical keywords"]
}}

Document Text:
\"\"\"
{truncated_text}
\"\"\"
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        if response and response.text:
            parsed = json.loads(response.text)
            parsed["source_id"] = source_id
            return parsed
    except Exception as e:
        logger.warning(f"Gemini API entity extraction failed for {source_id}: {e}. Using fallback.")

    return _extract_entities_fallback(truncated_text, source_id)


def entity_extraction_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Entity Extraction Node accepting and returning partial PatentPilotState.
    """
    raw_docs = state.get("raw_documents") or []
    extracted_entities = []

    for doc in raw_docs[:10]:  # Cap at 10 documents per run
        ent = extract_entities_from_doc(doc)
        if ent:
            extracted_entities.append(ent)

    return {"technical_entities": extracted_entities}
