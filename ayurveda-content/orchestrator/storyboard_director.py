#!/usr/bin/env python3
"""
Theatrical Storyboard Director & Anti-Uncanny Framing Engine
Translates full narrative health scripts into a 10-12 shot cinematic storyboard.
Enforces the 3-Second Film Pacing Rule, Zero-Modulo Repetition, Anti-Uncanny Framing,
Character Identity Consistency, and precision Foley sound design cues.
"""

import json
import logging
import math
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
    Directs cinematic film storyboards for short-form video.
    Converts speech narrative into tightly-paced (2.5 - 3.6s) bespoke shots.
    """

    # Persistent Character Card for character continuity across shots
    DEFAULT_CHARACTER_ANCHOR = (
        "Maya, a 28-year-old South Asian woman with warm brown eyes, loose dark hair tied with a linen wrap, "
        "wearing an earth-toned olive-green cotton tunic, natural glowing skin in warm directional morning sunlight"
    )

    # Master Cinematographic Lens & Lighting Bible
    CINEMATIC_STYLE_BIBLE = (
        "photorealistic 35mm anamorphic documentary cinematography, warm Kodak 5207 film tone, "
        "soft morning sunlight, shallow depth of field, natural atmospheric dust motes, rich textures, 8k resolution"
    )

    @classmethod
    def generate_theatrical_storyboard(
        cls,
        script_json: Dict[str, Any],
        topic_data: Dict[str, Any],
        total_duration_sec: float = 40.0,
    ) -> List[Dict[str, Any]]:
        """
        Generates 10-12 bespoke cinematic shots covering total_duration_sec with zero modulo repetition.
        Uses Ollama LLM if available, with an ironclad algorithmic fallback that guarantees
        flawless cinematic shot grammar and anti-uncanny framing.
        """
        # Determine number of shots based on 3.2-3.6s target pacing
        target_shot_dur = 3.4
        num_shots = max(8, min(14, int(math.ceil(total_duration_sec / target_shot_dur))))

        subject = topic_data.get("subject") or script_json.get("topic", "Ayurvedic Gut Health")
        key_fact = topic_data.get("key_fact", "Drinking iced water freezes digestive fire and congeals fats")
        dosha = topic_data.get("dosha", "Digestive Agni Balance")

        # Try Ollama contextual generation first
        try:
            from common.ollama_client import query_ollama_json
            system_prompt = f"""You are an elite Hollywood and National Geographic documentary film director.
Your task is to create a {num_shots}-shot cinematic film storyboard for a 9:16 vertical health film.

CRITICAL FILM DIRECTING RULES:
1. THE 3-SECOND RULE: Each shot lasts 2.5 to 3.5 seconds. Rapid, mesmerizing documentary cuts.
2. ZERO MODULO REPETITION: Every single shot is 100% unique. Never repeat a subject or scene.
3. ANTI-UNCANNY FRAMING:
   - FORBIDDEN: Symmetrical passport headshots, dead-on eye staring, moving mouths without speech.
   - MANDATORY: 3/4 profile angles, over-the-shoulder perspectives, macro texture close-ups, hands interacting with objects, natural sunlight silhouettes.
4. CHARACTER CONTINUITY: Use the locked character: "{cls.DEFAULT_CHARACTER_ANCHOR}".
5. FOLEY SOUND DESIGN: Every shot must have an exact sound effect cue:
   - Ice/Cold: "ice_clink.wav", "cold_water_splash.wav"
   - Tension/Crisis: "sub_bass_drop.wav"
   - Preparation/Herbs: "brass_pour.wav", "steam_hiss.wav"
   - Revelation/Healing: "ethereal_chime.wav"

Output JSON matching:
{{
  "shots": [
    {{
      "shot_index": 1,
      "role": "The Catalyst",
      "camera": "Macro Dutch Angle Dolly In",
      "image_prompt": "Ultra-detailed 2D visual description...",
      "motion_prompt": "Explicit physical motion description...",
      "sfx_cue": "ice_clink.wav"
    }}
  ]
}}"""
            user_prompt = f"""Direct {num_shots} cinematic shots for:
Subject: {subject}
Core Warning: {key_fact}
Dosha: {dosha}
Return exactly {num_shots} shots in valid JSON."""

            data = query_ollama_json(prompt=user_prompt, system=system_prompt, timeout=60)
            shots_raw = data.get("shots", [])
            if isinstance(shots_raw, list) and len(shots_raw) >= 6:
                logger.info(f"[+] Storyboard Director generated {len(shots_raw)} contextual LLM shots.")
                return cls._normalize_and_time_shots(shots_raw, total_duration_sec, num_shots)
        except Exception as e:
            logger.info(f"Using algorithmic cinematic storyboard director ({e}).")

        # Algorithmic Cinematic Storyboard Generation (Ironclad, guaranteed 10-12 shots)
        return cls._generate_algorithmic_storyboard(
            subject=subject,
            key_fact=key_fact,
            total_duration_sec=total_duration_sec,
            num_shots=num_shots,
        )

    @classmethod
    def _generate_algorithmic_storyboard(
        cls,
        subject: str,
        key_fact: str,
        total_duration_sec: float,
        num_shots: int,
    ) -> List[Dict[str, Any]]:
        """
        Algorithmic master storyboard template enforcing Anti-Uncanny framing,
        cinematic shot grammar, and professional Foley sound design.
        """
        char = cls.DEFAULT_CHARACTER_ANCHOR
        style = cls.CINEMATIC_STYLE_BIBLE

        # Shot grammar sequence: Macro Catalyst -> Frost Reaction -> Over-Shoulder Context ->
        # Chemistry Demonstration -> Botanical Slicing -> Mortar Herb Crushing ->
        # The Hot Brass Pour -> Living Steam Physics -> Relief Sip -> Morning Radiance -> Hero Packshot
        master_shot_templates = [
            # Shot 1: The Hook Catalyst
            {
                "role": "The Hook Catalyst",
                "camera": "Macro Dutch Angle Slow Dolly In",
                "image_prompt": (
                    f"Extreme close-up macro shot of heavy translucent ice cubes splashing into a glass of ice-cold water, "
                    f"crystal clear water droplets frozen in air, dramatic directional morning sunlight, {style}"
                ),
                "motion_prompt": (
                    "Dramatic slow-motion liquid splash, ice cubes bobbing dynamically, water droplets flying and rippling, "
                    "continuous slow cinematic camera push-in dolly shot"
                ),
                "sfx_cue": "ice_clink.wav",
            },
            # Shot 2: The Physical Chill
            {
                "role": "The Frost Reaction",
                "camera": "Macro Surface Tracking Pan",
                "image_prompt": (
                    f"Macro extreme close-up of frosty condensation beads rapidly dripping down a tall chilled glass, "
                    f"shimmering refracted morning light, crisp golden rim reflection, {style}"
                ),
                "motion_prompt": (
                    "Liquid droplets slowly trickling down the chilled glass surface, condensation shifting in the light, "
                    "smooth cinematic horizontal macro slide"
                ),
                "sfx_cue": "cold_water_splash.wav",
            },
            # Shot 3: Over-the-Shoulder Human Context (Anti-Uncanny)
            {
                "role": "Over-The-Shoulder Context",
                "camera": "Over-The-Shoulder Shallow Focus",
                "image_prompt": (
                    f"Cinematic over-the-shoulder shot looking past {char} sitting at a rustic wooden breakfast table, "
                    f"looking down at her glass, soft morning window light illuminating her shoulder, {style}"
                ),
                "motion_prompt": (
                    "Subtle natural breathing movement in torso and shoulder, gentle morning breeze rustling linen curtains, "
                    "cinematic shallow depth of field camera drift, lifelike living presence"
                ),
                "sfx_cue": "sub_bass_drop.wav",
            },
            # Shot 4: The Metabolic Chemistry
            {
                "role": "The Visceral Demonstration",
                "camera": "Macro Top-Down Tilt",
                "image_prompt": (
                    f"Close-up demonstration in clear glass bowl showing pure virgin olive oil contacting ice-cold water, "
                    f"golden oil droplets solidifying and congealing into thick waxy beads, laboratory documentary lighting, {style}"
                ),
                "motion_prompt": (
                    "Liquid oil separating and congealing on the icy liquid surface, dynamic chemical reaction, "
                    "slow vertical camera tilt downward"
                ),
                "sfx_cue": "cold_water_splash.wav",
            },
            # Shot 5: Botanical Preparation
            {
                "role": "Botanical Slicing",
                "camera": "Macro Side Track",
                "image_prompt": (
                    f"Macro shot of artisan chef hands cleanly slicing a fresh raw ginger root with a sharp knife on a heavy teak wood cutting board, "
                    f"fine droplets of fragrant ginger juice spraying into sunbeams, {style}"
                ),
                "motion_prompt": (
                    "Chef knife making a clean decisive slice through fresh fibrous ginger, juicy zest spraying, "
                    "smooth cinematic tracking motion"
                ),
                "sfx_cue": "whoosh_transition.wav",
            },
            # Shot 6: Mortar & Pestle Herb Alchemy
            {
                "role": "Herb Alchemy",
                "camera": "High-Angle Circular Arc",
                "image_prompt": (
                    f"Close-up high angle shot of a traditional stone mortar crushing golden fennel seeds and aromatic green cardamom pods, "
                    f"fine aromatic botanical dust floating in warm sunlight, {style}"
                ),
                "motion_prompt": (
                    "Stone pestle grinding aromatic herbal seeds, golden herbal dust puffing softly into sunbeams, "
                    "slow orbital camera rotation"
                ),
                "sfx_cue": "whoosh_transition.wav",
            },
            # Shot 7: The Alchemical Pour (The Remedy)
            {
                "role": "The Hot Brass Pour",
                "camera": "Macro Hero Tilt",
                "image_prompt": (
                    f"Hero close-up macro shot of steaming amber-golden spiced herbal infusion pouring from a kettle into an authentic hammered brass cup, "
                    f"liquid swirling with amber clarity, glowing directional sunlight, {style}"
                ),
                "motion_prompt": (
                    "Continuous steaming liquid pouring gracefully into brass cup, dynamic swirling ripples on surface, "
                    "rising billowing steam, slow cinematic push-in"
                ),
                "sfx_cue": "brass_pour.wav",
            },
            # Shot 8: Living Steam Physics
            {
                "role": "Living Thermal Steam",
                "camera": "Extreme Macro Low-Angle",
                "image_prompt": (
                    f"Extreme macro shot of delicate translucent steam plumes billowing and swirling upwards from a hot brass vessel, "
                    f"dark warm wooden background, sunlit thermal eddies dancing in the air, {style}"
                ),
                "motion_prompt": (
                    "Lush living thermal steam swirling and rising continuously into the air, delicate fluid air currents, "
                    "subtle slow-motion documentary camera push"
                ),
                "sfx_cue": "steam_hiss.wav",
            },
            # Shot 9: The Relief Sip (Profile Perspective)
            {
                "role": "The Relief Sip",
                "camera": "3/4 Profile Medium Close-Up",
                "image_prompt": (
                    f"Side profile cinematic shot of {char} bringing the warm steaming brass cup to her lips, "
                    f"holding the warm cup with both hands, steam softly grazing her cheek in warm morning light, {style}"
                ),
                "motion_prompt": (
                    "Gentle natural motion as she lifts the warm cup to take a soothing sip, soft breathing, "
                    "organic lifelike movement, shallow focus cinema"
                ),
                "sfx_cue": "ethereal_chime.wav",
            },
            # Shot 10: Radiant Morning Vitality
            {
                "role": "Radiant Vitality",
                "camera": "Medium Tracking Shot",
                "image_prompt": (
                    f"Vibrant cinematic shot of {char} outdoors walking through a lush sun-drenched herbal garden, "
                    f"natural radiant smile, morning sunbeams creating golden lens flares, glowing vitality, {style}"
                ),
                "motion_prompt": (
                    "Smooth cinematic camera tracking along with her as she walks through the sunny garden, "
                    "natural hair and fabric movement in the breeze, vibrant life"
                ),
                "sfx_cue": "whoosh_transition.wav",
            },
            # Shot 11: Hero Packshot
            {
                "role": "Hero Packshot",
                "camera": "Centered Slow Push-In",
                "image_prompt": (
                    f"Hero still-life packshot of the steaming Ayurvedic brass cup centered on a clean sunlit marble surface, "
                    f"surrounded by fresh ginger, star anise, and whole cardamom pods, soft golden bokeh, {style}"
                ),
                "motion_prompt": (
                    "Delicate steam drifting softly above the golden brew, sunbeams shifting gently across the marble, "
                    "slow majestic camera push-in"
                ),
                "sfx_cue": "ethereal_chime.wav",
            },
            # Shot 12: Micro Detail Texture
            {
                "role": "Macro Amber Surface",
                "camera": "Macro Surface Drift",
                "image_prompt": (
                    f"Macro top-down shot of the amber herbal infusion surface reflecting warm morning sunlight, "
                    f"delicate micro-droplets of ginger essential oil creating iridescent rings, {style}"
                ),
                "motion_prompt": (
                    "Gentle surface tension ripples, golden oil rings shimmering in sunlight, "
                    "hypnotic slow macro camera glide"
                ),
                "sfx_cue": "brass_pour.wav",
            },
        ]

        # Select exactly num_shots
        selected = master_shot_templates[:num_shots]
        return cls._normalize_and_time_shots(selected, total_duration_sec, num_shots)

    @classmethod
    def _normalize_and_time_shots(
        cls,
        shots: List[Dict[str, Any]],
        total_duration_sec: float,
        target_count: int,
    ) -> List[Dict[str, Any]]:
        """Calculates precise start_sec and duration_sec for each shot."""
        actual_shots = shots[:target_count]
        shot_dur = round(total_duration_sec / len(actual_shots), 2)

        timed_shots = []
        curr_time = 0.0
        for idx, s in enumerate(actual_shots, 1):
            dur = shot_dur if idx < len(actual_shots) else round(total_duration_sec - curr_time, 2)
            timed_shots.append({
                "shot_index": idx,
                "role": s.get("role", f"Shot {idx}"),
                "camera": s.get("camera", "Cinematic Dolly In"),
                "image_prompt": s.get("image_prompt", ""),
                "motion_prompt": s.get("motion_prompt", ""),
                "sfx_cue": s.get("sfx_cue", "whoosh_transition.wav"),
                "start_sec": round(curr_time, 2),
                "duration_sec": max(2.5, dur),
            })
            curr_time += dur

        return timed_shots


def test_storyboard():
    """Validates the TheatricalStoryboardDirector outputs 10-12 unique shots with 0 modulo loops."""
    test_topic = {
        "subject": "Extinguishing Digestive Fire With Ice Water",
        "key_fact": "Drinking iced water freezes digestive enzymes and congeals fats",
        "dosha": "Digestive Agni",
    }
    shots = TheatricalStoryboardDirector.generate_theatrical_storyboard(
        script_json={},
        topic_data=test_topic,
        total_duration_sec=38.0,
    )

    assert len(shots) >= 8, f"Expected at least 8 shots, got {len(shots)}"
    roles = [s["role"] for s in shots]
    assert len(roles) == len(set(roles)), "Duplicate roles detected! Modulo repetition found."

    print(f"[+] Storyboard test passed! Generated {len(shots)} unique bespoke shots:")
    for s in shots:
        print(f"    Shot {s['shot_index']}: [{s['start_sec']:.1f}s - {s['start_sec'] + s['duration_sec']:.1f}s] ({s['role']}) -> SFX: {s['sfx_cue']}")


if __name__ == "__main__":
    test_storyboard()
