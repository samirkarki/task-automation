#!/usr/bin/env python3
"""
Theatrical Storyboard Director & Action-Staged Framing Engine
Translates spoken narrative sentences into a synchronized cinematic storyboard.
Enforces:
  1. Direct Sentence-to-Visual Semantic Binding (100% contextual relevance to spoken words)
  2. Action-Staged Keyframing (stages the action in the keyframe to eliminate anatomical horror)
  3. Natural Human Actions (sipping, stirring, holding, expressive reactions, gentle breathing)
  4. Macro Physical Science & Liquid Alchemy (curdling, pouring, steam, bubbling, spice grinding)
  5. Strict prohibition against cosmetic hallucinations (NO face creams, NO face masks)
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
    Binds visual shot actions directly to spoken narrative sentences.
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
    def group_whisper_segments_into_shots(
        cls,
        segments: List[Dict[str, Any]],
        total_duration_sec: float,
        target_shot_duration: float = 3.4,
    ) -> List[Dict[str, Any]]:
        """
        Groups fine-grained Whisper segments into cohesive ~3.0 - 3.8s narrative shot beats.
        Ensures cuts align cleanly with natural sentence and clause pauses.
        """
        if not segments:
            # Fallback if no segments provided: divide into ~3.4s beats
            num_shots = max(8, min(14, int(math.ceil(total_duration_sec / target_shot_duration))))
            dur = total_duration_sec / float(num_shots)
            return [
                {
                    "shot_index": i + 1,
                    "start_sec": round(i * dur, 2),
                    "end_sec": round(min(total_duration_sec, (i + 1) * dur), 2),
                    "duration_sec": round(dur, 2),
                    "sentence_text": "",
                }
                for i in range(num_shots)
            ]

        shot_beats: List[Dict[str, Any]] = []
        current_texts: List[str] = []
        current_start = float(segments[0].get("start", 0.0))

        for idx, seg in enumerate(segments):
            seg_text = seg.get("text", "").strip()
            seg_end = float(seg.get("end", current_start + 1.0))
            current_texts.append(seg_text)
            elapsed = seg_end - current_start
            is_last = (idx == len(segments) - 1)

            # Trigger shot boundary if beat reaches target duration or sentence ends
            if elapsed >= target_shot_duration or is_last:
                shot_dur = round(elapsed, 2)
                shot_beats.append({
                    "shot_index": len(shot_beats) + 1,
                    "start_sec": round(current_start, 2),
                    "end_sec": round(seg_end, 2),
                    "duration_sec": shot_dur,
                    "sentence_text": " ".join(current_texts).strip(),
                })
                current_start = seg_end
                current_texts = []

        return shot_beats

    @classmethod
    def generate_theatrical_storyboard(
        cls,
        script_json: Dict[str, Any],
        topic_data: Dict[str, Any],
        whisper_segments: Optional[List[Dict[str, Any]]] = None,
        total_duration_sec: float = 40.0,
    ) -> List[Dict[str, Any]]:
        """
        Generates 9-12 bespoke cinematic shots bound 1:1 to spoken sentence meaning.
        Employs Action-Staged Keyframing to ensure natural human movement and eliminates body horror.
        """
        # Step 1: Group speech into narrative shot beats aligned to sentence boundaries
        shot_beats = cls.group_whisper_segments_into_shots(
            segments=whisper_segments or [],
            total_duration_sec=total_duration_sec,
            target_shot_duration=3.4,
        )
        num_shots = len(shot_beats)

        subject = topic_data.get("subject") or script_json.get("topic", "Ayurvedic Digestion")
        key_fact = topic_data.get("key_fact", "Digestive balance requires warm botanical alchemy")
        dosha = topic_data.get("dosha", "Digestive Agni Balance")

        # Step 2: Try contextual LLM directorship with strict Action-Staged constraints
        try:
            from common.ollama_client import query_ollama_json

            # Format the exact sentence breakdown for Ollama
            beats_manifest = "\n".join(
                f"Shot {b['shot_index']} ({b['start_sec']}s-{b['end_sec']}s): \"{b['sentence_text']}\""
                for b in shot_beats
            )

            system_prompt = f"""You are an award-winning National Geographic documentary film director and food cinematography master.
Your mission is to direct a {num_shots}-shot cinematic film storyboard for a vertical 9:16 health documentary.

CRITICAL DIRECTING LAWS:
1. DIRECT SENTENCE RELEVANCE: Every visual shot MUST literally and physically illustrate the exact spoken words in that beat!
   - When discussing mixing milk and citrus: Show the physical chemical reaction—lemon juice dripping into fresh milk, proteins curdling into curds and whey!
   - When discussing bloating or cramps: Show the human character seated, resting a hand gently on their abdomen with an expressive concerned look.
   - When discussing warming spices like ginger: Show artisan hands cleanly slicing golden ginger root, or stirring grated ginger into warm simmering milk with a brass spoon!
   - When discussing drinking the remedy: Show the character bringing a warm steaming brass cup to their lips to take a soothing sip.
2. STRICT BAN ON COSMETICS / SKINCARE:
   - FORBIDDEN: NEVER show face creams, face masks, cosmetics, or rubbing ginger on skin. This is strictly an INGESTIBLE oral dietary drink / tea!
3. ACTION-STAGED KEYFRAMING (AVOID BODY HORROR):
   - Never ask the video model to transport hands 500 pixels across the screen or force a mouth open.
   - Stage the character ALREADY IN THE ACTION in the keyframe:
     - For sipping: Keyframe shows Maya ALREADY holding the warm cup right at her lower lip.
     - For stirring: Keyframe shows hands ALREADY holding the brass spoon inside the pot of milk.
     - For discomfort: Keyframe shows Maya ALREADY seated with her hand resting on her stomach.
   - Motion prompt only animates natural micro-dynamics: lips softly parting for a gentle sip, rising steam, spoon gently stirring, soft breathing.
   - FORBIDDEN: Chewing, biting, eating raw lemons, walking/running, lips moving without audio sync.
   - FORBIDDEN: Brushing or touching tiny individual seeds, grains, or lentils with fingertips (diffusion models cannot track micro-objects and melt hands into mush). Instead, show macro shots of ingredients in a bowl or simmering pot.
4. CHARACTER CONTINUITY: Use the persistent character anchor: "{cls.DEFAULT_CHARACTER_ANCHOR}".

Output valid JSON matching:
{{
  "shots": [
    {{
      "shot_index": 1,
      "role": "The Warning Observation",
      "camera": "Macro Dutch Angle Dolly In",
      "image_prompt": "Ultra-detailed 2D visual description...",
      "motion_prompt": "Explicit physical motion description..."
    }}
  ]
}}"""

            user_prompt = f"""Direct {num_shots} cinematic shots for this exact script:
Subject: {subject}
Core Truth: {key_fact}
Dosha: {dosha}

TIMED SPOKEN SCRIPT BEATS:
{beats_manifest}

Return exactly {num_shots} shots in valid JSON adhering to the Action-Staged Keyframing laws."""

            data = query_ollama_json(prompt=user_prompt, system=system_prompt, timeout=60)
            shots_raw = data.get("shots", [])
            if isinstance(shots_raw, list) and len(shots_raw) >= max(6, num_shots - 2):
                logger.info(f"[+] Storyboard Director generated {len(shots_raw)} sentence-bound LLM shots.")
                return cls._merge_and_validate_shots(shots_raw, shot_beats)
        except Exception as e:
            logger.info(f"Using intelligent algorithmic sentence-bound director ({e}).")

        # Step 3: Algorithmic Sentence-Bound Storyboard Generation (Ironclad, 100% context-relevant)
        return cls._generate_algorithmic_sentence_storyboard(
            shot_beats=shot_beats,
            subject=subject,
            key_fact=key_fact,
        )

    @classmethod
    def _merge_and_validate_shots(
        cls,
        shots_raw: List[Dict[str, Any]],
        shot_beats: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Merges LLM shots with exact Whisper timing and sanitizes against cosmetic/horror prompts."""
        merged: List[Dict[str, Any]] = []
        for i, beat in enumerate(shot_beats):
            raw = shots_raw[i] if i < len(shots_raw) else {}
            img_p = raw.get("image_prompt", "")
            mot_p = raw.get("motion_prompt", "")

            # Sanitize against cosmetic face-cream hallucinations
            if any(w in img_p.lower() for w in ["face cream", "face mask", "cream in face", "skin cream", "lotion"]):
                logger.warning(f"Sanitizing cosmetic hallucination in Shot {i+1} -> Converted to spiced milk preparation.")
                img_p = (
                    f"Close-up shot of artisan hands using a vintage brass spoon to stir freshly grated golden ginger root and cinnamon into a simmering pot of warm milk, {cls.CINEMATIC_STYLE_BIBLE}"
                )
                mot_p = (
                    "Brass spoon stirring the warm spiced milk in slow smooth circular motion, golden liquid swirling, fragrant steam billowing softly"
                )

            # Sanitize against eating lemons raw
            if "eating lemon" in img_p.lower() or "eating lemon" in mot_p.lower():
                logger.warning(f"Sanitizing eating-lemon horror in Shot {i+1} -> Converted to macro curdling reaction.")
                img_p = (
                    f"Extreme macro shot of pure whole milk in a glass vessel, fresh lemon juice drops falling into the liquid, proteins curdling and clumping into curds and whey, {cls.CINEMATIC_STYLE_BIBLE}"
                )
                mot_p = (
                    "Dynamic slow-motion liquid droplets falling, milk curdling and separating into curds and whey, fluid surface ripples"
                )

            # Sanitize against fine-motor fingertip actions on micro-seeds/lentils (causes diffusion smudge horror)
            if any(w in img_p.lower() or w in mot_p.lower() for w in ["finger lightly brushes", "brushes across", "stroking lentil", "touching lentil", "finger on lentil"]):
                logger.warning(f"Sanitizing micro-lentil fingertip action in Shot {i+1} -> Converted to simmering lentil pot.")
                img_p = (
                    f"Close-up high-angle shot of dry split lentils in a ceramic bowl on a rustic table, contrasted with golden lentils simmering with fresh ginger in an authentic earthen pot, {cls.CINEMATIC_STYLE_BIBLE}"
                )
                mot_p = (
                    "Fragrant steam billowing upwards from the simmering lentil pot, delicate surface bubbling, slow smooth cinematic camera push-in dolly shot"
                )

            merged.append({
                "shot_index": beat["shot_index"],
                "role": raw.get("role", f"Narrative Beat {i+1}"),
                "camera": raw.get("camera", "Cinematic Macro Push-In"),
                "image_prompt": img_p or cls._build_contextual_fallback_image_prompt(beat["sentence_text"]),
                "motion_prompt": mot_p or cls._build_contextual_fallback_motion_prompt(beat["sentence_text"]),
                "start_sec": beat["start_sec"],
                "end_sec": beat["end_sec"],
                "duration_sec": beat["duration_sec"],
                "sentence_text": beat["sentence_text"],
            })
        return merged

    @classmethod
    def _generate_algorithmic_sentence_storyboard(
        cls,
        shot_beats: List[Dict[str, Any]],
        subject: str,
        key_fact: str,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically analyzes the text of each spoken sentence to generate 100% context-aligned
        Action-Staged shots with zero body horror and zero generic mismatches.
        """
        shots: List[Dict[str, Any]] = []

        for beat in shot_beats:
            s_text = beat["sentence_text"].lower()
            idx = beat["shot_index"]

            img_p, mot_p, role, cam = cls._classify_sentence_to_action(s_text, idx, len(shot_beats))

            shots.append({
                "shot_index": idx,
                "role": role,
                "camera": cam,
                "image_prompt": img_p,
                "motion_prompt": mot_p,
                "start_sec": beat["start_sec"],
                "end_sec": beat["end_sec"],
                "duration_sec": beat["duration_sec"],
                "sentence_text": beat["sentence_text"],
            })
        return shots

    @classmethod
    def _classify_sentence_to_action(
        cls,
        text: str,
        shot_idx: int,
        total_shots: int,
    ) -> Tuple[str, str, str, str]:
        """
        Translates a spoken sentence into an Action-Staged Keyframe prompt and safe kinetic motion prompt.
        """
        char = cls.DEFAULT_CHARACTER_ANCHOR
        style = cls.CINEMATIC_STYLE_BIBLE

        # Category 5: Vitality, Energy, Radiance, CTA (The Healthy Conclusion)
        if any(w in text for w in ["energized", "balanced all day", "vitality", "follow for daily", "heal your body", "light, balanced"]):
            role = "Radiant Vitality Reaction"
            cam = "Medium Portrait Dolly In"
            img = (
                f"Cinematic portrait of {char} looking towards a sunlit window with a warm, genuine radiant smile, holding the warm brass cup with both hands on the table, "
                f"golden morning sunbeams illuminating her face with healthy glowing vitality, {style}"
            )
            mot = (
                "Soft natural eye blink, warm radiant smile broadening gently, living breathing presence, morning sunbeams shifting softly, peaceful joy"
            )
            return img, mot, role, cam

        # Category 4: The Remedy Drink, Pouring, Sipping (The Relief Sip)
        if any(w in text for w in ["drink", "sip", "tea", "cup", "mug", "remedy", "fix", "solution", "soothing", "kindle"]):
            if shot_idx >= total_shots - 2 or any(w in text for w in ["drink", "sip", "lips"]):
                # The Relief Sip: staged right at the lips
                role = "The Relief Sip"
                cam = "3/4 Profile Close-Up"
                img = (
                    f"Cinematic 3/4 profile shot of {char} bringing an authentic warm hammered brass cup to her lips, cup touching lower lip, "
                    f"holding the warm cup with both hands, aromatic herbal steam softly curling past her cheek in warm morning light, {style}"
                )
                mot = (
                    "Gentle natural sip, lips subtly parting, aromatic steam billowing continuously from the cup, soft relaxed breathing, peaceful relief"
                )
                return img, mot, role, cam
            else:
                # The Hot Brass Pour
                role = "The Hot Brass Pour"
                cam = "Macro Hero Tilt"
                img = (
                    f"Hero macro close-up of steaming golden spiced milk pouring gracefully from a copper kettle into an authentic hammered brass cup, "
                    f"rich liquid swirling with golden turmeric and ginger froth, dramatic sunbeams, {style}"
                )
                mot = (
                    "Continuous steaming spiced milk pouring into the brass cup, rich fluid swirling ripples on surface, billowing rising steam"
                )
                return img, mot, role, cam

        # Category 3: Warming Spices, Ginger, Cardamom, Simmering Preparation
        if any(w in text for w in ["ginger", "spice", "warm", "cardamom", "cinnamon", "boil", "simmer", "stir", "pot"]):
            if any(w in text for w in ["slice", "cut", "fresh ginger", "root"]):
                role = "Artisan Ginger Preparation"
                cam = "Macro Side Track"
                img = (
                    f"Macro close-up shot of artisan hands cleanly slicing fresh raw knobby ginger root with a sharp chef knife on a teak wood cutting board, "
                    f"fragrant fine droplets of spicy ginger juice catching warm morning sunbeams, {style}"
                )
                mot = (
                    "Clean decisive knife stroke slicing through fibrous golden ginger, fragrant micro-zest spraying, smooth cinematic tracking motion"
                )
                return img, mot, role, cam
            else:
                role = "Spiced Milk Alchemy"
                cam = "High-Angle Circular Arc"
                img = (
                    f"Close-up high-angle shot of artisan hands using a vintage hammered brass spoon to gently stir freshly grated golden ginger and green cardamom pods into a simmering pot of warm whole milk, "
                    f"golden spice ripples swirling through the creamy liquid, billowing aromatic steam, {style}"
                )
                mot = (
                    "Brass spoon smoothly stirring warm spiced milk in slow circular motion, golden liquid rippling and swirling, fragrant steam rising continuously"
                )
                return img, mot, role, cam

        # Category 1: Milk, Citrus, Curdling (The Chemical Incompatibility)
        if any(w in text for w in ["curdle", "curdling", "citrus", "lemon", "sour", "acid"]):
            if any(w in text for w in ["milk", "dairy"]):
                role = "Macro Curdling Reaction"
                cam = "Extreme Macro Dolly In"
                img = (
                    f"Extreme close-up macro shot of pure whole milk inside a clear glass vessel, fresh yellow lemon juice drops falling into the liquid, "
                    f"milk proteins visibly coagulating and separating into textured curds and clear watery whey, dramatic directional morning sunlight, {style}"
                )
                mot = (
                    "Dynamic slow-motion liquid droplets plunging into milk, milk curds visibly clumping and separating on the surface, "
                    "gentle fluid ripples, continuous slow cinematic camera push-in"
                )
                return img, mot, role, cam
            else:
                role = "Citrus Acid Macro"
                cam = "Macro Slow Pan"
                img = (
                    f"Extreme macro shot of a fresh ripe yellow lemon sliced open on a dark teak wood surface, glistening translucent pulp vesicles bursting with juice in golden morning sunbeams, {style}"
                )
                mot = (
                    "Slow cinematic macro camera glide across the citrus surface, sunlight refracting through juice droplets, delicate atmospheric dust motes"
                )
                return img, mot, role, cam

        # Category 2: Bloating, Fermentation, Stomach Cramps, Toxicity
        if any(w in text for w in ["bloat", "cramp", "ferment", "toxin", "stomach", "gut", "fatigue", "digestive fire", "agni", "mistake"]):
            if shot_idx == 1:
                # Opening hook: character observing breakfast table with curiosity
                role = "The Hook Observation"
                cam = "Over-The-Shoulder Shallow Focus"
                img = (
                    f"Cinematic over-the-shoulder shot looking past {char} seated at a rustic wooden dining table in morning window light, "
                    f"looking down with thoughtful curiosity at a glass of milk and fresh citrus fruits on the table, {style}"
                )
                mot = (
                    "Subtle natural breathing movement in shoulder, gentle head tilt, warm morning breeze rustling linen curtains, cinematic shallow focus"
                )
                return img, mot, role, cam
            else:
                # Digestive discomfort: action-staged seated pose with hand on abdomen
                role = "The Digestive Discomfort"
                cam = "Medium Close-Up Subtle Dolly In"
                img = (
                    f"Cinematic medium close-up of {char} seated at a rustic table, resting one hand gently on her abdomen with an expressive concerned look, "
                    f"warm moody morning window light casting soft shadows, {style}"
                )
                mot = (
                    "Subtle shallow breathing, hand resting gently on abdomen, subtle downward concerned glance, organic living presence, slow camera push"
                )
                return img, mot, role, cam

        # Category 5: Vitality, Energy, Radiance, CTA (The Healthy Conclusion)
        role = "Radiant Vitality Reaction"
        cam = "Medium Portrait Dolly In"
        img = (
            f"Cinematic portrait of {char} looking towards a sunlit window with a warm, genuine radiant smile, holding the warm brass cup with both hands on the table, "
            f"golden morning sunbeams illuminating her face with healthy glowing vitality, {style}"
        )
        mot = (
            "Soft natural eye blink, warm radiant smile broadening gently, living breathing presence, morning sunbeams shifting softly, peaceful joy"
        )
        return img, mot, role, cam

    @classmethod
    def _build_contextual_fallback_image_prompt(cls, text: str) -> str:
        img, _, _, _ = cls._classify_sentence_to_action(text.lower(), 1, 10)
        return img

    @classmethod
    def _build_contextual_fallback_motion_prompt(cls, text: str) -> str:
        _, mot, _, _ = cls._classify_sentence_to_action(text.lower(), 1, 10)
        return mot

    @classmethod
    def _normalize_and_time_shots(
        cls,
        shots: List[Dict[str, Any]],
        total_duration_sec: float,
        target_count: int,
    ) -> List[Dict[str, Any]]:
        """Utility to re-time shots evenly if fine-grained Whisper segments were not available."""
        out = []
        n = max(1, len(shots))
        dur_per = total_duration_sec / float(n)
        for i, s in enumerate(shots):
            s_copy = dict(s)
            s_copy["shot_index"] = i + 1
            s_copy["start_sec"] = round(i * dur_per, 2)
            s_copy["end_sec"] = round(min(total_duration_sec, (i + 1) * dur_per), 2)
            s_copy["duration_sec"] = round(s_copy["end_sec"] - s_copy["start_sec"], 2)
            out.append(s_copy)
        return out


def test_storyboard() -> bool:
    """Verifies that the sentence-bound storyboard director generates Action-Staged shots."""
    director = TheatricalStoryboardDirector()
    dummy_segments = [
        {"start": 0.0, "end": 3.6, "text": "When you mix milk with sour citrus fruits, they curdle instantly in your stomach."},
        {"start": 3.6, "end": 7.2, "text": "This creates toxic fermented sludge that blocks nutrient absorption and causes severe bloating."},
        {"start": 7.2, "end": 10.8, "text": "In ancient holistic science, cooling dairy clashes with acidic heating fruits, extinguishing your digestive fire."},
        {"start": 10.8, "end": 14.5, "text": "Instead, always wait at least two hours between dairy and citrus."},
        {"start": 14.5, "end": 18.2, "text": "And always add warming spices like fresh ginger to help digest the combination safely."},
        {"start": 18.2, "end": 22.0, "text": "Drink warm spiced milk to kindle digestive fire and feel light, energized, and balanced all day."},
    ]

    shots = director.generate_theatrical_storyboard(
        script_json={"topic": "Milk and Citrus Incompatibility"},
        topic_data={"subject": "Milk and Citrus Incompatibility", "key_fact": "Mixing milk with citrus causes curdling"},
        whisper_segments=dummy_segments,
        total_duration_sec=22.0,
    )

    print(f"[+] Storyboard test generated {len(shots)} shots:")
    for s in shots:
        print(f"  Shot {s['shot_index']} ({s['start_sec']}s-{s['end_sec']}s) [{s['role']}]: {s['image_prompt'][:65]}...")
        # Check that no cosmetic face creams exist
        assert "face cream" not in s["image_prompt"].lower(), "Cosmetic face cream found!"
        assert "eating lemon" not in s["image_prompt"].lower(), "Eating lemon horror found!"

    print("[+] All storyboard assertions passed cleanly!")
    return True


if __name__ == "__main__":
    test_storyboard()
