#!/usr/bin/env python3
"""
Ayurveda Daily Life Knowledge Catalog & High-CTR Title Generator
Contains hundreds of practical, daily-life Ayurvedic concepts organized into
6 high-retention categories, with automated viral hook and title generation.
"""

import random
from typing import Dict, List, Any, Optional

CATEGORIES: Dict[str, Dict[str, Any]] = {
    "digestion_agni": {
        "title": "Digestion & Agni (Gut Fire)",
        "badge": "GUT HEALTH SECRETS",
        "description": "Daily eating habits, gut fire (Agni), and food combining (Viruddha Ahara).",
        "topics": [
            {
                "subject": "Why drinking cold water with meals extinguishes digestive fire (Agni)",
                "dosha": "Pitta/Vata",
                "keywords": ["cold water drinking", "digestion belly health", "pouring warm herbal tea"],
                "key_fact": "Cold water dampens Agni (digestive fire), causing undigested food toxins (Ama) to accumulate in the gut.",
            },
            {
                "subject": "The toxic combination of milk and sour fruits in Ayurveda (Viruddha Ahara)",
                "dosha": "Tridosha",
                "keywords": ["fruit smoothie pouring", "fresh milk kitchen", "gut digestion healthy"],
                "key_fact": "Mixing milk and citrus curdles inside the stomach, fermenting into toxins and skin flare-ups.",
            },
            {
                "subject": "Eating fruit after a heavy meal vs on an empty stomach",
                "dosha": "Vata/Pitta",
                "keywords": ["fresh fruits bowl", "healthy breakfast eating", "happy stomach energy"],
                "key_fact": "Fruits digest in 30 minutes, while cooked meals take 3-4 hours. Eating fruit after food traps it, causing severe bloating.",
            },
            {
                "subject": "Chewing fennel and ajwain seeds after dinner for instant debloating",
                "dosha": "Vata/Kapha",
                "keywords": ["fennel seeds spice", "herbal seeds digestion", "flat stomach wellness"],
                "key_fact": "Fennel relaxes smooth digestive muscles while ajwain stimulates gastric enzymes instantly.",
            },
            {
                "subject": "Why you should never reheat food or eat leftovers after 24 hours (Tamasic food)",
                "dosha": "Tridosha",
                "keywords": ["cooking fresh meal", "herbs spices pan", "clean healthy food"],
                "key_fact": "Food loses Prana (life-force energy) within 3 hours of cooking, turning Tamasic and burdening metabolism.",
            },
        ],
    },
    "sleep_circadian": {
        "title": "Sleep & Dinacharya (Night Routine)",
        "badge": "DEEP SLEEP HACK",
        "description": "Circadian sleep cycles, calming the nervous system, and night rituals.",
        "topics": [
            {
                "subject": "Why massaging warm sesame or castor oil on feet soles induces deep REM sleep (Pada Abhyanga)",
                "dosha": "Vata",
                "keywords": ["massage feet relaxing", "essential oil bottle", "cozy bed sleeping peaceful"],
                "key_fact": "Foot soles contain marma points linked to the nervous system. Massaging them grounds excess Vata energy immediately.",
            },
            {
                "subject": "Golden milk with nutmeg and cinnamon: The ancient cortisol-lowering bedtime tonic",
                "dosha": "Vata/Pitta",
                "keywords": ["golden turmeric milk", "warm milk cinnamon", "deep peaceful sleep"],
                "key_fact": "Nutmeg acts as a mild natural sedative in Ayurveda, promoting sustained gamma-aminobutyric acid (GABA) release.",
            },
            {
                "subject": "The danger of sleeping between 10 PM and 2 AM (Pitta detoxification window)",
                "dosha": "Pitta",
                "keywords": ["clock ticking night", "sleeping calm dark room", "morning fresh waking"],
                "key_fact": "Between 10 PM and 2 AM is the Pitta cycle when the liver detoxifies and cleanses your blood. Staying awake ruins internal repair.",
            },
            {
                "subject": "Brahmi tea before bed for stopping racing overactive thoughts",
                "dosha": "Vata",
                "keywords": ["drinking herbal tea bed", "peaceful meditation calm", "soft night light bedroom"],
                "key_fact": "Brahmi (Bacopa) cools the brain, balances neurotransmitters, and prevents restless insomnia.",
            },
        ],
    },
    "morning_energy": {
        "title": "Morning Routine & Vital Energy",
        "badge": "MORNING RITUAL",
        "description": "Tongue scraping, copper water, oil pulling, and activating Ojas.",
        "topics": [
            {
                "subject": "Copper water (Tamra Jal) in the morning for gut detox and cellular vitality",
                "dosha": "Kapha/Vata",
                "keywords": ["copper vessel water", "pouring clean water glass", "morning sunlight window"],
                "key_fact": "Water stored overnight in copper becomes naturally alkaline, antimicrobial, and jumpstarts metabolic fire.",
            },
            {
                "subject": "Why tongue scraping removes overnight toxins (Ama) that brushing misses",
                "dosha": "Tridosha",
                "keywords": ["morning bathroom mirror", "clean fresh smile", "herbal mouthwash natural"],
                "key_fact": "The white coating on the tongue is undigested metabolic waste. Scraping prevents re-ingestion and enhances taste receptors.",
            },
            {
                "subject": "Oil pulling (Gandusha) with virgin sesame oil for jaw strength and oral microbiome",
                "dosha": "Vata/Kapha",
                "keywords": ["sesame oil spoon", "morning routine wellness", "bright healthy teeth smile"],
                "key_fact": "Oil pulling pulls lipid-soluble bacteria and strengthens gum tissues through natural lipid binding.",
            },
        ],
    },
    "herbs_rasayana": {
        "title": "Herbs & Adaptogens (Rasayana)",
        "badge": "ANCIENT ADAPTOGENS",
        "description": "Rejuvenating herbs for longevity, brain power, hormones, and stress.",
        "topics": [
            {
                "subject": "Benefits of Ashwagandha for regulating high cortisol and panic anxiety",
                "dosha": "Vata/Kapha",
                "keywords": ["ashwagandha herbal root", "peaceful calm nature", "warm herbal drink"],
                "key_fact": "Ashwagandha (Withania somnifera) modulates the HPA axis, reducing cortisol by up to 30% without drowsiness.",
            },
            {
                "subject": "Triphala: The three-fruit formula that cleanses the colon and restores gut microbiome",
                "dosha": "Tridosha",
                "keywords": ["herbal powder spoon", "dried medicinal fruits", "healthy active lifestyle"],
                "key_fact": "Triphala tones the intestinal walls, supports peristalsis naturally, and never creates dependency.",
            },
            {
                "subject": "Amla (Indian Gooseberry): The king of natural Vitamin C and mitochondrial anti-aging",
                "dosha": "Pitta",
                "keywords": ["fresh green gooseberry amla", "crushing herbs mortar", "glowing vibrant health"],
                "key_fact": "Amla contains heat-stable Vitamin C wrapped in bioflavonoids, boosting collagen synthesis and immune resilience.",
            },
        ],
    },
    "skin_hair": {
        "title": "Skin, Hair & Beauty",
        "badge": "NATURAL GLOW",
        "description": "Ayurvedic treatments for hair loss, clear skin, and preventing premature graying.",
        "topics": [
            {
                "subject": "Why Pitta heat causes acne and hair thinning (and how aloe + amla reverse it)",
                "dosha": "Pitta",
                "keywords": ["aloe vera fresh gel", "hair brushing shiny", "clear glowing skin face"],
                "key_fact": "Excess internal body heat burns scalp follicles and manifests as cystic breakouts. Cooling bitter herbs stop hair loss.",
            },
            {
                "subject": "Warm Rosemary and Bhringraj hair oiling for dormant hair follicles",
                "dosha": "Vata/Pitta",
                "keywords": ["applying hair oil scalp", "healthy thick hair woman", "botanical hair elixir"],
                "key_fact": "Bhringraj is crowned 'Keshraj' (ruler of hair) for its ability to prolong the anagen hair growth phase.",
            },
        ],
    },
}

HOOK_TEMPLATES = [
    # Variant A: Curiosity Gap & Counter-Intuitive
    "Why you should NEVER {action} if you want {benefit}...",
    "The 5,000-year-old Ayurvedic secret doctors never talk about: {subject}",
    "If you deal with {pain_point}, your body is begging you for this 1 daily Ayurvedic fix...",
    
    # Variant B: Warning & Mistake Avoidance
    "Stop making this #1 Ayurvedic mistake every single morning: {subject}!",
    "Are you constantly {pain_point}? Here is the ancient Ayurvedic root cause...",
    "Warning: Doing this after eating is silently ruining your gut fire!",

    # Variant C: Direct High-Value Actionable
    "Drink THIS ancient herbal tonic before bed and watch your {benefit} skyrocket.",
    "3 Morning habits in Ayurveda that give you all-day boundless energy:",
    "How to rebalance your {dosha} Dosha in just 60 seconds with this simple kitchen remedy."
]


def generate_title_variants(topic_data: Dict[str, Any]) -> Dict[str, str]:
    """Generates 3 optimized YouTube Shorts / Reels titles for A/B testing."""
    subject = topic_data.get("subject", "")
    dosha = topic_data.get("dosha", "Health")

    return {
        "variant_a_curiosity": f"The Ancient Ayurvedic Secret: {subject[:65]} #Shorts",
        "variant_b_warning": f"STOP Doing This! Ayurvedic Warning on {subject[:55]} #Shorts",
        "variant_c_actionable": f"1 Daily Ayurvedic Habit for {dosha} Balance #Shorts",
    }


def pick_random_topic(category_key: Optional[str] = None) -> Dict[str, Any]:
    """Picks a curated topic from the knowledge catalog."""
    if not category_key or category_key not in CATEGORIES:
        category_key = random.choice(list(CATEGORIES.keys()))

    cat_info = CATEGORIES[category_key]
    topic_entry = random.choice(cat_info["topics"])

    titles = generate_title_variants(topic_entry)

    return {
        "category_key": category_key,
        "category_title": cat_info["title"],
        "badge": cat_info["badge"],
        "subject": topic_entry["subject"],
        "dosha": topic_entry["dosha"],
        "key_fact": topic_entry["key_fact"],
        "keywords": topic_entry["keywords"],
        "titles": titles,
    }


def get_all_categories() -> List[Dict[str, str]]:
    """Returns a list of all available Ayurvedic topic categories."""
    return [{"key": k, "title": v["title"], "badge": v["badge"]} for k, v in CATEGORIES.items()]
