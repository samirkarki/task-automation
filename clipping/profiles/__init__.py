"""
Profile registry and dynamic profile loader.
"""

from typing import Dict, List, Optional
from clipping.profiles.base import ClipProfile
from clipping.profiles.gta6 import GTA6_PROFILE
from clipping.profiles.fortnite import FORTNITE_PROFILE
from clipping.profiles.mrbeast import MRBEAST_PROFILE
from clipping.profiles.business import BUSINESS_PROFILE

PROFILE_REGISTRY: Dict[str, ClipProfile] = {
    "game-gta6": GTA6_PROFILE,
    "gta6": GTA6_PROFILE,
    "game-fortnite": FORTNITE_PROFILE,
    "fortnite": FORTNITE_PROFILE,
    "mrbeast": MRBEAST_PROFILE,
    "business": BUSINESS_PROFILE,
    "business_wealth": BUSINESS_PROFILE,
}

DEFAULT_PROFILE = GTA6_PROFILE


def get_profile(name: Optional[str] = None) -> ClipProfile:
    """
    Returns the ClipProfile instance for the given name.
    Falls back to GTA6_PROFILE if name is None or not found.
    """
    if not name:
        return DEFAULT_PROFILE
    key = name.lower().strip()
    return PROFILE_REGISTRY.get(key, DEFAULT_PROFILE)


def list_profiles() -> List[str]:
    """Returns list of unique registered profile names."""
    return sorted(list(set(p.name for p in PROFILE_REGISTRY.values())))
