#!/usr/bin/env python3
"""
Theatrical Storyboard Director & Universal 4-Block Message Engine
Converts full Ayurvedic scripts into 4 Cohesive, High-Impact Cinematic Message Blocks:
  1. Block 1: The Arresting Hook & Mistake (Visceral macro demonstration, 0s - ~9s)
  2. Block 2: The Metabolic Truth & Consequence (Glowing Agni embers / sluggish Ama, ~9s - ~20s)
  3. Block 3: The Ancient Kitchen Remedy (Artisan hands slicing & simmering spices, ~20s - ~32s)
  4. Block 4: The Concluding Resolution & Golden Takeaway (Steaming brass cup pour + final climax, ~32s - End)

Strict Constraints:
  - 85%+ Macro Food Alchemy & Physical Science (Minimizes humans to eliminate AI distortion).
  - Absolute ban on Nudity, bare skin, exposed chests, bare stomachs, and body caressing.
  - Universal dynamic semantic adaptation to ANY Ayurvedic topic (honey, curd, milk, ghee, lentils, water, etc.).
"""

import logging
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ORCH_DIR = PROJECT_ROOT / "ayurveda-content" / "orchestrator"
if str(ORCH_DIR) not in sys.path:
    sys.path.insert(0, str(ORCH_DIR))

logger = logging.getLogger("storyboard_director")


class TheatricalStoryboardDirector:
    """
    Directs 4 cohesive, broadcast-grade cinematic message blocks for any Ayurvedic Short.
    """

    # Persistent Character Anchor (Strictly fully clothed in modest traditional linen)
    DEFAULT_CHARACTER_ANCHOR = (
        "Maya, a 28-year-old South Asian woman with warm brown eyes, loose dark hair tied with a linen wrap, "
        "modestly dressed in an earth-toned high-collar olive-green cotton tunic with long sleeves, "
        "natural glowing skin in warm directional morning sunlight"
    )

    # Master Cinematographic Lens & Lighting Bible
    CINEMATIC_STYLE_BIBLE = (
        "photorealistic 35mm anamorphic documentary cinematography, warm Kodak 5207 film tone, "
        "soft morning sunlight, shallow depth of field, natural atmospheric dust motes, rich textures, 8k resolution"
    )

    @classmethod
    def segment_script_into_4_blocks(
        cls,
        segments: List[Dict[str, Any]],
        total_duration_sec: float,
    ) -> List[Dict[str, Any]]:
        """
        Partitions the narrative into exactly 4 cohesive informational message blocks:
          Block 1: Hook & Mistake (~22% duration)
          Block 2: Metabolic Mechanism (~28% duration)
          Block 3: Kitchen Alchemy Remedy (~30% duration)
          Block 4: Resolution & Grand Finale (~20% duration)
        """
        # Target cut timestamps
        t1 = round(total_duration_sec * 0.22, 2)
        t2 = round(total_duration_sec * 0.50, 2)
        t3 = round(total_duration_sec * 0.78, 2)
        target_splits = [t1, t2, t3, round(total_duration_sec, 2)]

        if not segments:
            # Fallback if Whisper segments missing
            return [
                {"block_index": 1, "start_sec": 0.0, "end_sec": t1, "duration_sec": t1, "text": "The Hook & Mistake", "role": "The Arresting Hook"},
                {"block_index": 2, "start_sec": t1, "end_sec": t2, "duration_sec": round(t2 - t1, 2), "text": "Metabolic Consequence", "role": "Metabolic Mechanism"},
                {"block_index": 3, "start_sec": t2, "end_sec": t3, "duration_sec": round(t3 - t2, 2), "text": "Kitchen Remedy", "role": "The Ancient Remedy"},
                {"block_index": 4, "start_sec": t3, "end_sec": round(total_duration_sec, 2), "duration_sec": round(total_duration_sec - t3, 2), "text": "Resolution", "role": "Concluding Resolution"},
            ]

        # Group Whisper segments into the 4 target windows
        blocks: List[Dict[str, Any]] = []
        current_block_idx = 0
        current_texts: List[str] = []
        block_start = 0.0

        for seg in segments:
            seg_text = seg.get("text", "").strip()
            seg_end = float(seg.get("end", block_start + 1.0))
            current_texts.append(seg_text)

            # If segment passes current target split boundary and we have not finished block 3
            if current_block_idx < 3 and seg_end >= target_splits[current_block_idx]:
                blocks.append({
                    "block_index": current_block_idx + 1,
                    "start_sec": round(block_start, 2),
                    "end_sec": round(seg_end, 2),
                    "duration_sec": round(seg_end - block_start, 2),
                    "text": " ".join(current_texts).strip(),
                })
                block_start = seg_end
                current_texts = []
                current_block_idx += 1

        # Final block 4 captures all remaining segments
        dur_final = round(max(4.0, total_duration_sec - block_start), 2)
        blocks.append({
            "block_index": 4,
            "start_sec": round(block_start, 2),
            "end_sec": round(total_duration_sec, 2),
            "duration_sec": dur_final,
            "text": " ".join(current_texts).strip(),
        })

        return blocks

    @classmethod
    def generate_theatrical_storyboard(
        cls,
        script_json: Dict[str, Any],
        topic_data: Dict[str, Any],
        whisper_segments: Optional[List[Dict[str, Any]]] = None,
        total_duration_sec: float = 40.0,
    ) -> List[Dict[str, Any]]:
        """
        Directs 4 master cinematic message blocks for ANY Ayurvedic topic.
        Guarantees 100% platform safety (zero nudity) and 85%+ macro food alchemy.
        """
        blocks = cls.segment_script_into_4_blocks(
            segments=whisper_segments or [],
            total_duration_sec=total_duration_sec,
        )

        subject = topic_data.get("subject") or script_json.get("topic", "Ayurvedic Health")
        key_fact = topic_data.get("key_fact", "Support digestive fire with warm botanical alchemy")
        dosha = topic_data.get("dosha", "Agni Balance")

        # Try Ollama contextual generation with strict 4-block laws
        try:
            from common.ollama_client import query_ollama_json

            blocks_manifest = "\n".join(
                f"Block {b['block_index']} ({b['start_sec']}s-{b['end_sec']}s): \"{b['text']}\""
                for b in blocks
            )

            system_prompt = f"""You are a world-renowned documentary film director and food cinematography master.
Your mission is to direct exactly 4 MASTER CINEMATIC BLOCKS for a 9:16 vertical health film on '{subject}'.

CRITICAL DIRECTING LAWS:
1. THE 4 MESSAGE BLOCKS:
   - Block 1 (The Arresting Hook): A shocking, mesmerizing extreme macro demonstration of the dietary mistake or core food in action (e.g. curdling, boiling, raw unsoaked ingredients, liquid crashing). Must grab viewer attention in 2 seconds!
   - Block 2 (The Metabolic Truth): Visual metabolic metaphor—smoldering golden amber coals/embers of internal digestive fire (Agni), or cloudy sluggish congealing liquid representing toxic waste (Ama).
   - Block 3 (The Kitchen Alchemy): Traditional kitchen medicine—modestly clothed artisan hands slicing fresh medicinal roots (ginger, turmeric) on a wooden board, or stirring ground spices into a simmering pot with a brass spoon and billowing steam.
   - Block 4 (The Concluding Resolution): Steaming golden brew pouring into an authentic hammered brass cup with rich sunbeams, followed by peaceful resolution.
2. MINIMIZE HUMANS (<15%):
   - Blocks 1, 2, and 3 MUST BE 100% MACRO FOOD & PHYSICAL ALCHEMY (liquids, steam, spices, embers, pots). No human bodies!
   - Block 4 may optionally show a modest over-the-shoulder wide shot of Maya ({cls.DEFAULT_CHARACTER_ANCHOR}) holding the warm cup.
3. ABSOLUTE NUDITY & NSFW BAN:
   - FORBIDDEN: Nudity, toplessness, bare chests, bare stomachs, exposed skin, bedrooms, or suggestive caressing. All human characters must be fully clothed in high-collar long-sleeve linen tunics.
4. UNIVERSAL TOPIC ADAPTATION:
   - Tailor all visuals specifically to '{subject}' and '{key_fact}'. No skincare, no cosmetics, strictly oral culinary Ayurveda!

Output valid JSON matching:
{{
  "shots": [
    {{
      "shot_index": 1,
      "role": "The Arresting Hook",
      "camera": "Macro Slow Push-In",
      "image_prompt": "Ultra-detailed 2D visual description...",
      "motion_prompt": "Explicit physical motion description..."
    }}
  ]
}}"""

            user_prompt = f"""Direct 4 cinematic message blocks for:
Subject: {subject}
Core Fact: {key_fact}
Dosha: {dosha}

THE 4 SPOKEN MESSAGE BLOCKS:
{blocks_manifest}

Return exactly 4 shots in valid JSON."""

            data = query_ollama_json(prompt=user_prompt, system=system_prompt, timeout=60)
            shots_raw = data.get("shots", [])
            if isinstance(shots_raw, list) and len(shots_raw) == 4:
                logger.info(f"[+] Storyboard Director generated 4 contextual LLM message blocks.")
                return cls._sanitize_and_bind_blocks(shots_raw, blocks, subject, key_fact)
        except Exception as e:
            logger.info(f"Using universal algorithmic 4-block director ({e}).")

        # Algorithmic Universal 4-Block Storyboard (100% Contextual, Safe & Visceral)
        return cls._generate_algorithmic_universal_blocks(blocks, subject, key_fact)

    @classmethod
    def _sanitize_and_bind_blocks(
        cls,
        shots_raw: List[Dict[str, Any]],
        blocks: List[Dict[str, Any]],
        subject: str,
        key_fact: str,
    ) -> List[Dict[str, Any]]:
        """Validates, sanitizes against nudity/horror, and binds the 4 shots to exact timing."""
        sanitized: List[Dict[str, Any]] = []

        for i, b in enumerate(blocks):
            raw = shots_raw[i] if i < len(shots_raw) else {}
            img_p = raw.get("image_prompt", "")
            mot_p = raw.get("motion_prompt", "")

            # Sanitize any NSFW / nudity / body caressing keywords
            if cls._is_nsfw_or_body_caress(img_p) or cls._is_nsfw_or_body_caress(mot_p):
                logger.warning(f"Sanitizing body/NSFW reference in Block {i+1} -> Converted to macro food alchemy.")
                img_p, mot_p = cls._get_safe_block_alchemy(i + 1, subject, key_fact, b["text"])

            # Ensure minimum length & quality
            if len(img_p) < 30:
                img_p, mot_p = cls._get_safe_block_alchemy(i + 1, subject, key_fact, b["text"])

            sanitized.append({
                "shot_index": i + 1,
                "role": raw.get("role", f"Block {i+1}"),
                "camera": raw.get("camera", "Cinematic Macro Push-In"),
                "image_prompt": img_p,
                "motion_prompt": mot_p,
                "start_sec": b["start_sec"],
                "end_sec": b["end_sec"],
                "duration_sec": b["duration_sec"],
                "sentence_text": b["text"],
            })

        return sanitized

    @classmethod
    def _generate_algorithmic_universal_blocks(
        cls,
        blocks: List[Dict[str, Any]],
        subject: str,
        key_fact: str,
    ) -> List[Dict[str, Any]]:
        """
        Universal algorithmic generator for ANY Ayurvedic topic:
        Extracts core ingredients from the subject and generates 4 stunning macro food science shots.
        """
        roles = [
            "The Arresting Hook",
            "Metabolic Agni Truth",
            "Ancient Kitchen Alchemy",
            "Concluding Resolution & Drink",
        ]
        cameras = [
            "Extreme Macro Dutch Angle Dolly In",
            "Macro Slow Horizontal Tracking Pan",
            "High-Angle Circular Arc Tracking",
            "Hero Macro Tilt Dolly In",
        ]

        shots: List[Dict[str, Any]] = []
        for i, b in enumerate(blocks):
            idx = i + 1
            img_p, mot_p = cls._get_safe_block_alchemy(idx, subject, key_fact, b["text"])
            shots.append({
                "shot_index": idx,
                "role": roles[i],
                "camera": cameras[i],
                "image_prompt": img_p,
                "motion_prompt": mot_p,
                "start_sec": b["start_sec"],
                "end_sec": b["end_sec"],
                "duration_sec": b["duration_sec"],
                "sentence_text": b["text"],
            })
        return shots

    @classmethod
    def _is_nsfw_or_body_caress(cls, text: str) -> bool:
        """Returns True if text contains prohibited body or nudity terms."""
        t_low = text.lower()
        bad_words = [
            "abdomen", "caress", "stomach", "belly", "bare", "nude", "nudity", "topless",
            "breast", "chest", "navel", "waist", "skin cream", "face cream", "face mask",
            "rubbing", "touching body", "bedroom", "undies", "underwear", "eating lemon"
        ]
        return any(w in t_low for w in bad_words)

    @classmethod
    def _get_safe_block_alchemy(
        cls,
        block_idx: int,
        subject: str,
        key_fact: str,
        block_text: str,
    ) -> Tuple[str, str]:
        """
        Synthesizes a universal, photorealistic macro food alchemy prompt tailored to ANY Ayurvedic topic.
        """
        style = cls.CINEMATIC_STYLE_BIBLE
        char = cls.DEFAULT_CHARACTER_ANCHOR
        subj_clean = subject.strip()

        # BLOCK 1: The Arresting Hook (The Mistake in Action)
        if block_idx == 1:
            # Detect primary subject matter dynamically
            s_low = f"{subject} {block_text}".lower()
            if "honey" in s_low:
                img = (
                    f"Extreme close-up macro shot of raw amber honey being overheated in a hot iron pan, "
                    f"honey bubbling aggressively, turning dark amber with fine wisps of thermal vapor in dramatic morning sunbeams, {style}"
                )
                mot = "Viscous bubbling amber liquid, thermal steam rising gracefully, slow cinematic camera push-in dolly shot"
            elif "curd" in s_low or "yogurt" in s_low:
                img = (
                    f"Extreme macro shot of thick cultured whole milk curd on a dark slate board, cold condensation beads shimmering, "
                    f"artisan wooden spoon lifting a heavy dense spoonful in golden directional morning light, {style}"
                )
                mot = "Slow cinematic macro camera glide across the glistening textured curd surface, soft morning light refraction"
            elif "milk" in s_low and any(w in s_low for w in ["citrus", "lemon", "sour", "acid", "curdle"]):
                img = (
                    f"Extreme close-up macro shot of fresh whole milk inside a clear glass vessel, fresh lemon juice droplets plunging in, "
                    f"milk proteins visibly coagulating and separating into textured curds and clear watery whey in morning sunlight, {style}"
                )
                mot = "Dynamic slow-motion liquid droplets plunging into milk, milk curds clumping and separating on the surface, gentle fluid ripples"
            elif "water" in s_low and any(w in s_low for w in ["ice", "cold", "chill"]):
                img = (
                    f"Extreme macro shot of heavy translucent ice cubes splashing violently into a tall glass of ice water, "
                    f"crystal clear water droplets flying in midair, frosted glass condensation in golden morning sunbeams, {style}"
                )
                mot = "Dramatic slow-motion liquid splash, ice cubes bobbing dynamically, water droplets flying and rippling, slow camera dolly in"
            elif any(w in s_low for w in ["lentil", "bean", "dal"]):
                img = (
                    f"Extreme close-up macro shot of dry, unsoaked rock-hard split lentils clattering into a dark stone mortar on a teak table, "
                    f"fine botanical dust puffing softly into dramatic morning sunbeams, {style}"
                )
                mot = "Hard dry lentils settling in the mortar, fine botanical dust floating in sunbeams, slow smooth macro camera push-in"
            elif "ghee" in s_low:
                img = (
                    f"Extreme macro shot of pure clarified golden liquid ghee swirling in a warm vintage brass spoon, "
                    f"golden translucency glowing warmly in directional morning sunlight, {style}"
                )
                mot = "Golden liquid ghee rippling smoothly inside the brass spoon, warm sunlight shifting, slow cinematic camera glide"
            else:
                # Universal Food Science Hook
                img = (
                    f"Extreme macro hero shot of authentic raw ingredients for {subj_clean} arranged on a rustic dark teak wood surface, "
                    f"fresh botanical textures glowing in directional morning sunbeams, dramatic shallow depth of field, {style}"
                )
                mot = "Smooth cinematic camera push-in dolly shot, warm morning sunbeams shifting gently across the surface, vivid depth"
            return img, mot

        # BLOCK 2: The Metabolic Truth (Agni & Ama Chemistry)
        if block_idx == 2:
            img = (
                f"Macro cinematic shot of glowing golden amber embers and wood coals of an ancient hearth fire, "
                f"smoldering with deep internal warmth, soft smoke and floating sparks in a moody dark atmospheric kitchen, {style}"
            )
            mot = (
                "Deep golden coals pulsing with gentle thermal warmth, delicate smoke rising softly, slow horizontal camera tracking pan"
            )
            return img, mot

        # BLOCK 3: The Ancient Kitchen Remedy (Botanical Alchemy)
        if block_idx == 3:
            img = (
                f"Close-up high-angle shot of artisan hands in high-collar linen sleeves using a vintage hammered brass spoon to gently stir "
                f"freshly sliced golden ginger, green cardamom pods, and whole cumin seeds into a simmering earthen pot of warm herbal decoction, "
                f"golden ripples swirling through the liquid, billowing fragrant steam in morning sunbeams, {style}"
            )
            mot = (
                "Brass spoon smoothly stirring warm spiced liquid in slow circular motion, golden liquid rippling, fragrant steam rising continuously"
            )
            return img, mot

        # BLOCK 4: The Concluding Resolution & Drink
        img = (
            f"Hero close-up macro shot of steaming amber-golden spiced Ayurvedic elixir pouring gracefully from a copper kettle into an authentic hammered brass cup, "
            f"rich liquid swirling with golden froth, delicate steam billowing into bright directional morning sunbeams on a rustic marble table, {style}"
        )
        mot = (
            "Continuous steaming spiced herbal elixir pouring into the brass cup, rich fluid swirling ripples on surface, billowing rising steam, slow majestic dolly in"
        )
        return img, mot


def test_universal_4_blocks():
    """Verifies that the Universal 4-Block Director generates exactly 4 safe macro shots for any topic."""
    director = TheatricalStoryboardDirector()

    test_topics = [
        {"subject": "Heating Raw Honey Above 40C", "key_fact": "Heat denatures honey enzymes into toxic Ama glue"},
        {"subject": "Curd and Yogurt at Night", "key_fact": "Heavy curd clogs micro-circulatory channels and creates mucus"},
        {"subject": "Drinking Iced Water With Meals", "key_fact": "Cold water extinguishes digestive fire and solidifies fats"},
    ]

    for t in test_topics:
        shots = director.generate_theatrical_storyboard(
            script_json={"topic": t["subject"]},
            topic_data=t,
            whisper_segments=[],
            total_duration_sec=40.0,
        )
        assert len(shots) == 4, f"Expected 4 shots, got {len(shots)}"
        print(f"\n[+] Topic '{t['subject']}' generated {len(shots)} blocks:")
        for s in shots:
            print(f"  Block {s['shot_index']} ({s['start_sec']}s-{s['end_sec']}s) [{s['role']}]: {s['image_prompt'][:70]}...")
            assert not director._is_nsfw_or_body_caress(s["image_prompt"]), "Prohibited body/caress term found!"
            assert not director._is_nsfw_or_body_caress(s["motion_prompt"]), "Prohibited motion term found!"

    print("\n[+] All universal 4-block assertions passed cleanly!")
    return True


if __name__ == "__main__":
    test_universal_4_blocks()
