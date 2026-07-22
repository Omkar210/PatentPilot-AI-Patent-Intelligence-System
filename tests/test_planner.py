"""
tests/test_planner.py — Unit Tests for Stage 2 Planner Agent

Tests the planner_agent_node function in agents/planner.py covering:
- Gemini LLM execution and response parsing
- Markdown codeblock stripping
- Groq LLM fallback when Gemini fails
- Rule-based NLP fallback when no API keys are configured
- Handling of empty / whitespace user queries
- Boundary clamping of keywords (guaranteed 3 to 6 keywords)
- LangGraph state dictionary compliance
"""

import sys
import unittest.mock as mock
import pytest
from typing import Dict, Any, List

from state import PatentPilotState
from agents.planner import (
    planner_agent_node,
    parse_keywords_json,
    extract_keywords_rule_based,
    clamp_keywords,
    _is_valid_api_key,
    DEFAULT_FALLBACK_KEYWORDS,
)


def test_is_valid_api_key():
    """Test helper for validating environment API keys."""
    assert not _is_valid_api_key(None)
    assert not _is_valid_api_key("")
    assert not _is_valid_api_key("   ")
    assert not _is_valid_api_key("your-google-gemini-api-key-here")
    assert not _is_valid_api_key("YOUR-GROQ-API-KEY-HERE")
    assert not _is_valid_api_key("placeholder_key")
    assert _is_valid_api_key("AIzaSyA1234567890abcdef")
    assert _is_valid_api_key("gsk_1234567890abcdef")


def test_parse_keywords_json_formats():
    """Test parse_keywords_json with raw array, markdown codeblock, JSON object, and regex fallback."""
    # Raw JSON array
    raw_array = '["vision transformer", "object detection", "autonomous vehicle"]'
    assert parse_keywords_json(raw_array) == ["vision transformer", "object detection", "autonomous vehicle"]

    # Markdown codeblock with json tag
    markdown_json = '```json\n["deep learning", "convolutional neural network", "pattern recognition"]\n```'
    assert parse_keywords_json(markdown_json) == ["deep learning", "convolutional neural network", "pattern recognition"]

    # Markdown codeblock without json tag
    markdown_plain = '```\n["spatial embedding", "vector search", "similarity index"]\n```'
    assert parse_keywords_json(markdown_plain) == ["spatial embedding", "vector search", "similarity index"]

    # JSON dict with search_keywords key
    dict_json = '{"search_keywords": ["transformer model", "natural language", "text processing"]}'
    assert parse_keywords_json(dict_json) == ["transformer model", "natural language", "text processing"]

    # JSON dict with keywords key
    dict_json2 = '{"keywords": ["quantum computing", "qubit control", "error correction"]}'
    assert parse_keywords_json(dict_json2) == ["quantum computing", "qubit control", "error correction"]

    # Quoted fallback regex
    quoted_text = 'Here are the recommended keywords: "feature extraction", "image segmentation", "classification".'
    assert parse_keywords_json(quoted_text) == ["feature extraction", "image segmentation", "classification"]


def test_planner_gemini_success(monkeypatch):
    """Test Gemini primary LLM path when valid GOOGLE_API_KEY is present."""
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy_test_gemini_valid_key")
    monkeypatch.setenv("GROQ_API_KEY", "your-groq-api-key-here")

    mock_response = mock.MagicMock()
    mock_response.text = '["vision transformer", "object detection", "pedestrian tracking"]'

    mock_model = mock.MagicMock()
    mock_model.generate_content.return_value = mock_response

    mock_genai = mock.MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

    state: PatentPilotState = {"user_query": "Pedestrian detection using vision transformers in autonomous cars"}
    result = planner_agent_node(state)

    assert "search_keywords" in result
    assert result["search_keywords"] == ["vision transformer", "object detection", "pedestrian tracking"]
    assert len(result["search_keywords"]) == 3


def test_planner_markdown_codeblock_stripping(monkeypatch):
    """Test that markdown codeblock wrappers from Gemini are cleanly stripped."""
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy_test_gemini_valid_key")
    monkeypatch.setenv("GROQ_API_KEY", "your-groq-api-key-here")

    mock_response = mock.MagicMock()
    mock_response.text = (
        "```json\n"
        "[\"convolutional neural network\", \"feature map\", \"transfer learning\", \"image classification\"]\n"
        "```"
    )

    mock_model = mock.MagicMock()
    mock_model.generate_content.return_value = mock_response

    mock_genai = mock.MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

    state: PatentPilotState = {"user_query": "Image classification with CNN feature maps and transfer learning"}
    result = planner_agent_node(state)

    assert result["search_keywords"] == [
        "convolutional neural network",
        "feature map",
        "transfer learning",
        "image classification"
    ]
    assert len(result["search_keywords"]) == 4


def test_planner_groq_fallback_when_gemini_fails(monkeypatch):
    """Test falling back to Groq when Gemini fails or raises an exception."""
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy_test_gemini_valid_key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_groq_valid_key")

    # Mock Gemini throwing an exception
    mock_genai = mock.MagicMock()
    mock_genai.GenerativeModel.side_effect = RuntimeError("Gemini API rate limit exceeded")
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

    # Mock Groq succeeding
    mock_groq_choice = mock.MagicMock()
    mock_groq_choice.message.content = '["groq keyword 1", "groq keyword 2", "groq keyword 3", "groq keyword 4"]'

    mock_groq_response = mock.MagicMock()
    mock_groq_response.choices = [mock_groq_choice]

    mock_groq_client = mock.MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response

    mock_groq_module = mock.MagicMock()
    mock_groq_module.Groq.return_value = mock_groq_client

    monkeypatch.setitem(sys.modules, "groq", mock_groq_module)

    state: PatentPilotState = {"user_query": "Query that causes Gemini rate limit error"}
    result = planner_agent_node(state)

    assert result["search_keywords"] == ["groq keyword 1", "groq keyword 2", "groq keyword 3", "groq keyword 4"]
    assert len(result["search_keywords"]) == 4


def test_planner_rule_based_fallback_no_api_keys(monkeypatch):
    """Test rule-based fallback execution when no valid API keys are present."""
    monkeypatch.setenv("GOOGLE_API_KEY", "your-google-gemini-api-key-here")
    monkeypatch.setenv("GROQ_API_KEY", "your-groq-api-key-here")

    state: PatentPilotState = {
        "user_query": "System and method for autonomous vehicle navigation using vision transformers and lidar sensors"
    }

    result = planner_agent_node(state)

    assert "search_keywords" in result
    keywords = result["search_keywords"]
    assert isinstance(keywords, list)
    assert 3 <= len(keywords) <= 6
    # Verify technical terms/phrases extracted
    joined_kws = " ".join(keywords).lower()
    assert any(term in joined_kws for term in ["autonomous vehicle", "vision transformers", "lidar sensors", "navigation"])


def test_planner_empty_user_query(monkeypatch):
    """Test handling of empty, None, or whitespace-only user queries."""
    monkeypatch.setenv("GOOGLE_API_KEY", "your-google-gemini-api-key-here")
    monkeypatch.setenv("GROQ_API_KEY", "your-groq-api-key-here")

    # Empty string
    res1 = planner_agent_node({"user_query": ""})
    assert res1["search_keywords"] == DEFAULT_FALLBACK_KEYWORDS
    assert len(res1["search_keywords"]) == 3

    # Whitespace string
    res2 = planner_agent_node({"user_query": "   \n\t  "})
    assert res2["search_keywords"] == DEFAULT_FALLBACK_KEYWORDS
    assert len(res2["search_keywords"]) == 3

    # Empty dictionary (no user_query key)
    res3 = planner_agent_node({})
    assert res3["search_keywords"] == DEFAULT_FALLBACK_KEYWORDS
    assert len(res3["search_keywords"]) == 3


def test_planner_keyword_count_boundary_clamping(monkeypatch):
    """Test strict clamping of keyword count to between 3 and 6 items."""
    monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSy_test_gemini_valid_key")

    # Subtest 1: LLM returns only 1 keyword -> must pad to at least 3
    mock_response_short = mock.MagicMock()
    mock_response_short.text = '["single keyword"]'
    mock_model_short = mock.MagicMock()
    mock_model_short.generate_content.return_value = mock_response_short
    mock_genai_short = mock.MagicMock()
    mock_genai_short.GenerativeModel.return_value = mock_model_short
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai_short)

    res_short = planner_agent_node({"user_query": "quantum computing qubit error correction"})
    assert len(res_short["search_keywords"]) >= 3
    assert "single keyword" in res_short["search_keywords"]

    # Subtest 2: LLM returns 8 keywords -> must truncate to exactly 6
    mock_response_long = mock.MagicMock()
    mock_response_long.text = '["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7", "kw8"]'
    mock_model_long = mock.MagicMock()
    mock_model_long.generate_content.return_value = mock_response_long
    mock_genai_long = mock.MagicMock()
    mock_genai_long.GenerativeModel.return_value = mock_model_long
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai_long)

    res_long = planner_agent_node({"user_query": "Long list test query"})
    assert len(res_long["search_keywords"]) == 6
    assert res_long["search_keywords"] == ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6"]


def test_planner_state_dict_return_schema():
    """Test compliance with PatentPilotState typing and return dictionary structure."""
    state: PatentPilotState = {"user_query": "Deep reinforcement learning for robot control"}
    result = planner_agent_node(state)

    assert isinstance(result, dict)
    assert "search_keywords" in result
    keywords = result["search_keywords"]
    assert isinstance(keywords, list)
    assert 3 <= len(keywords) <= 6
    for kw in keywords:
        assert isinstance(kw, str)
        assert len(kw.strip()) > 0
