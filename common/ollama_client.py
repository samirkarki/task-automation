#!/usr/bin/env python3
"""
Unified, Resilient Ollama REST API Client
Provides structured generation, automatic model fallbacks, markdown fence stripping,
and strict JSON parsing across all automation modules.
"""

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Union
import requests

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("common.ollama_client")

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate"))
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", os.getenv("OLLAMA_PRIMARY_MODEL", "qwen3-coder:30b"))
DEFAULT_FALLBACK_MODELS = [
    os.getenv("OLLAMA_FALLBACK_MODEL", "llama3.1:8b"),
    "llama3:latest",
]


def strip_markdown_blocks(text: str) -> str:
    """Strips Markdown code fences (e.g., ```json ... ```) from LLM output."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def extract_json(raw_text: str) -> Dict[str, Any]:
    """Cleans markdown blocks and strictly parses JSON with bracket matching fallback."""
    cleaned = strip_markdown_blocks(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start : end + 1])
        raise


def query_ollama(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    fallback_models: Optional[List[str]] = None,
    enforce_json: bool = True,
    timeout: int = 120,
    api_url: Optional[str] = None,
) -> str:
    """
    Sends a generation request to the local/remote Ollama instance.
    Automatically tries fallback models if the primary model is unavailable.
    """
    endpoint = api_url or DEFAULT_OLLAMA_URL
    primary_model = model or DEFAULT_MODEL
    fallbacks = fallback_models if fallback_models is not None else DEFAULT_FALLBACK_MODELS
    candidates = [primary_model] + [m for m in fallbacks if m != primary_model]

    last_error = None
    for target_model in candidates:
        logger.info(f"Querying Ollama model '{target_model}' at {endpoint}...")
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if enforce_json:
            payload["format"] = "json"

        try:
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "").strip()
            if not response_text:
                raise ValueError(f"Empty response from Ollama model '{target_model}'")
            return response_text

        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Cannot reach Ollama at {endpoint}. Ensure Ollama is running ('ollama serve').")
            raise conn_err
        except requests.exceptions.HTTPError as http_err:
            logger.warning(f"Model '{target_model}' returned HTTP {resp.status_code}. Trying next model...")
            last_error = http_err
        except Exception as err:
            logger.warning(f"Error querying model '{target_model}': {err}")
            last_error = err

    raise RuntimeError(f"All Ollama models failed ({candidates}). Last error: {last_error}")


def query_ollama_json(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    fallback_models: Optional[List[str]] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Queries Ollama and parses the response into a structured JSON dict."""
    raw_response = query_ollama(
        prompt=prompt,
        system=system,
        model=model,
        fallback_models=fallback_models,
        enforce_json=True,
        timeout=timeout,
    )
    return extract_json(raw_response)
