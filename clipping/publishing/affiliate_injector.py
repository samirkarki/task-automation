"""
Affiliate & Bridge Page Injector for Day-1 Monetization.
Structures compliant, high-converting descriptions, affiliate links, and pinned comment CTAs.
"""

import logging
from typing import Dict, Any
from clipping.config import (
    BRIDGE_PAGE_URL,
    TELEGRAM_COMMUNITY_LINK,
    AFFILIATE_LINKS,
    DESCRIPTION_TEMPLATE,
    PINNED_COMMENT_TEMPLATE,
)

logger = logging.getLogger("clipping.publishing.affiliate_injector")


def inject_monetization_links(
    summary_text: str,
    original_creator: str,
    custom_cta: str = None,
) -> Dict[str, str]:
    """
    Builds the full monetized description and pinned comment.
    Avoids raw suspicious affiliate links by using a clean Bridge Page (Beacons/Carrd).
    """
    summary_clean = summary_text.strip()
    if len(summary_clean) > 200:
        summary_clean = summary_clean[:197] + "..."

    description = DESCRIPTION_TEMPLATE.format(
        summary=summary_clean,
        bridge_page_url=BRIDGE_PAGE_URL,
        telegram_link=TELEGRAM_COMMUNITY_LINK,
        newsletter_link=AFFILIATE_LINKS.get("newsletter", BRIDGE_PAGE_URL),
        original_creator=original_creator or "Host & Guest",
    )

    pinned_comment = PINNED_COMMENT_TEMPLATE.format(
        bridge_page_url=BRIDGE_PAGE_URL,
    )

    return {
        "description": description.strip(),
        "pinned_comment": pinned_comment.strip(),
    }
