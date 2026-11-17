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
import time
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
    timeout: int = 240,
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
            logger.warning(
                f"Connection dropped or unreachable for model '{target_model}' at {endpoint}: {conn_err}. "
                "Pausing 3s before retry/fallback..."
            )
            last_error = conn_err
            time.sleep(3)
        except requests.exceptions.HTTPError as http_err:
            logger.warning(f"Model '{target_model}' returned HTTP {getattr(resp, 'status_code', 'error')}. Trying next model...")
            last_error = http_err
        except Exception as err:
            logger.warning(f"Error querying model '{target_model}': {err}")
            last_error = err

    raise RuntimeError(f"All Ollama models failed ({candidates}). Last error: {last_error}")


def unload_ollama_model(model: Optional[str] = None, api_url: Optional[str] = None) -> bool:
    """
    Immediately unloads the given model from GPU VRAM by sending keep_alive: 0.
    Frees VRAM for subsequent GPU workloads like ComfyUI DiT video generation.
    """
    target_model = model or DEFAULT_MODEL
    endpoint = api_url or DEFAULT_OLLAMA_URL
    try:
        resp = requests.post(
            endpoint,
            json={"model": target_model, "keep_alive": 0},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info(f"[+] Unloaded Ollama model '{target_model}' from GPU VRAM (keep_alive: 0).")
            return True
    except Exception as e:
        logger.debug(f"Could not unload Ollama model '{target_model}': {e}")
    return False


def unload_all_ollama_models(base_url: Optional[str] = None) -> bool:
    """
    Discovers all currently loaded models in Ollama via /api/ps and evicts them
    from GPU VRAM by sending keep_alive: 0, guaranteeing maximum VRAM for ComfyUI.
    """
    gen_endpoint = base_url or DEFAULT_OLLAMA_URL
    # Derive root host: e.g. http://localhost:11434 from http://localhost:11434/api/generate
    ps_endpoint = gen_endpoint.split("/api/")[0] + "/api/ps"
    generate_endpoint = gen_endpoint.split("/api/")[0] + "/api/generate"

    unloaded_any = False
    models_to_unload = set([DEFAULT_MODEL, "qwen3-coder:30b", "llama3.1:8b"] + DEFAULT_FALLBACK_MODELS)

    # 1. Query /api/ps for active running models
    try:
        ps_resp = requests.get(ps_endpoint, timeout=5)
        if ps_resp.status_code == 200:
            active_models = ps_resp.json().get("models", [])
            for m in active_models:
                m_name = m.get("name") or m.get("model")
                if m_name:
                    models_to_unload.add(m_name)
    except Exception as ps_err:
        logger.debug(f"Could not query Ollama /api/ps ({ps_err}). Evicting standard candidate models...")

    # 2. Evict each model with keep_alive: 0
    for target_model in models_to_unload:
        try:
            resp = requests.post(
                generate_endpoint,
                json={"model": target_model, "keep_alive": 0},
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(f"[+] Evicted Ollama model '{target_model}' from GPU VRAM.")
                unloaded_any = True
        except Exception:
            pass

    return unloaded_any


def query_ollama_json(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    fallback_models: Optional[List[str]] = None,
    timeout: int = 240,
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
