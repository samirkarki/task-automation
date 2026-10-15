#!/usr/bin/env python3
"""
Root Proxy Entry Point for Premium Video Engine
Redirects execution to narrative_warfare.premium_video_engine.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from narrative_warfare.premium_video_engine import main

if __name__ == "__main__":
    main()
