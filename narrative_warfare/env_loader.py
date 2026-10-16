#!/usr/bin/env python3
"""
Environment Variable Loader for Task Automation Pipeline
Guarantees that .env files from the project root or current working directory
are cleanly parsed and populated into os.environ across all submodules.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("env_loader")

_LOADED = False


def load_project_env(custom_path: Optional[Path] = None, force_reload: bool = False) -> bool:
    """
    Loads key-value pairs from .env into os.environ.
    Safe to call multiple times (idempotent unless force_reload=True).
    """
    global _LOADED
    if _LOADED and not force_reload:
        return True

    env_paths = []
    if custom_path:
        env_paths.append(Path(custom_path).resolve())

    # Check project root (.env)
    root_dir = Path(__file__).resolve().parent.parent
    env_paths.append(root_dir / ".env")

    # Check current working directory
    env_paths.append(Path.cwd() / ".env")

    found_path = None
    for p in env_paths:
        if p.is_file():
            found_path = p
            break

    if not found_path:
        # No .env found, which is valid if environment variables are set in OS/systemd
        return False

    # 1. Try python-dotenv if available
    try:
        import dotenv
        dotenv.load_dotenv(dotenv_path=str(found_path), override=False)
        logger.debug(f"[ENV] Loaded environment via python-dotenv from {found_path}")
        _LOADED = True
        return True
    except ImportError:
        pass

    # 2. Resilient built-in parser fallback
    try:
        with open(found_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip wrapping single or double quotes
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    # Only set if key is not already defined in environment or is empty
                    if key and (key not in os.environ or not os.environ[key]):
                        os.environ[key] = val
        logger.debug(f"[ENV] Loaded environment via native parser from {found_path}")
        _LOADED = True
        return True
    except Exception as e:
        logger.warning(f"[ENV] Failed to parse .env file at {found_path}: {e}")
        return False


# Execute immediately upon module import
load_project_env()
