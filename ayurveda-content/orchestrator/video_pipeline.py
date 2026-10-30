#!/usr/bin/env python3
"""
Ayurveda End-to-End Automated Video Pipeline
Orchestrates:
1. Topic selection from Ayurveda Knowledge Catalog (or custom topic)
2. High-CTR script generation via Ollama LLM with audience feedback tuning
3. Neural audio generation via Kokoro-82M TTS (or Edge-TTS fallback)
4. Word-level timestamp extraction via OpenAI Whisper
5. Pexels 9:16 portrait stock footage download
6. Remotion CLI rendering (1080x1920 MP4 with kinetic bouncy captions & progress bar)
7. Performance analytics logging & Multi-Platform Publishing (YouTube, TikTok, Instagram)
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Globally disable cuDNN right after importing PyTorch to prevent CUDNN_STATUS_NOT_INITIALIZED
import torch
torch.backends.cudnn.enabled = False

from common.env_loader import load_project_env
load_project_env()

from common.ollama_client import query_ollama_json
from common.tts_engine import synthesize_with_kokoro, synthesize_with_edge
from common.whisper_utils import transcribe_audio_words
from common.stock_media import download_batch_stock_videos
from common.publishing import publish_to_all_platforms
from common.audio_mastering import master_voice_with_ambient

from topic_catalog import pick_random_topic, generate_title_variants, CATEGORIES
from analytics_feedback import AyurvedaAnalyticsDB, FeedbackOptimizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ayurveda.pipeline")


def build_system_prompt_with_feedback(feedback_directive: str) -> str:
    """Builds the LLM system prompt injected with live audience performance feedback."""
    return f"""You are an elite holistic health doctor and viral social media video scriptwriter.
Your goal is to produce engaging, medically intuitive Ayurvedic wisdom scripts optimized for Western and international audiences (YouTube Shorts, Instagram Reels, TikTok).

{feedback_directive}

CRITICAL RULES:
1. Output ONLY valid, raw JSON. Do not include markdown code fences (like ```json), no preamble, no commentary.
2. DURATION & WORD COUNT: Target video duration is 45-55 seconds. The spoken script MUST be between 110 and 135 words total.
3. LANGUAGE & NATIVE ENGLISH TRANSLATIONS: Write in fluent, natural English. You MUST translate or immediately explain all traditional Sanskrit terms into plain English for an English-speaking audience:
   - 'Agni' -> explain as 'your internal digestive fire' or 'stomach digestive heat'.
   - 'Ama' -> explain as 'toxic undigested waste' or 'metabolic sludge'.
   - 'Dosha' -> explain as 'body constitution' or 'metabolic balance'.
   - 'Viruddha Ahara' -> explain as 'incompatible food combinations'.
   NEVER leave raw untranslated Sanskrit words alone in the spoken voiceover. The narration must be phonetically smooth and natural for English speech synthesis.
4. SCRIPT STRUCTURE (40-60s Retention Architecture):
   - "hook": High-energy curiosity hook that addresses a common everyday habit (12-16 words).
   - "body": Structured explanation (85-105 words):
     * Explain the hidden biological mechanism (why cold water/habit halts gastric enzymes and digestive fire).
     * Explain the toxic consequence (undigested food fermenting into toxic sludge, bloating, and fatigue).
     * Provide 1 actionable ancient remedy with clear instructions (sip warm water, ginger tea, or chew seeds).
   - "cta": Compelling invitation to follow for daily gut health and holistic wellness secrets (10-14 words).
5. VISUAL SEARCH QUERIES: Provide 6 to 8 specific, high-retention cinematic search queries matching each phase of the script in chronological order (e.g. pouring ice water, stomach anatomy, bloated belly discomfort, pouring hot herbal tea, slicing fresh ginger, healthy energized person).

Output exact JSON schema:
{{
  "topic": "Clean topic name",
  "category": "Category name",
  "visual_search_queries": [
    "query 1: hook visual",
    "query 2: stomach/anatomy visual",
    "query 3: mistake/reaction visual",
    "query 4: consequence/discomfort visual",
    "query 5: fermenting/toxin visual",
    "query 6: ancient fix/warm tea visual",
    "query 7: preparation/spices visual",
    "query 8: vitality/happy wellness visual"
  ],
  "english_script": {{
    "hook": "Opening hook sentence.",
    "body": "Detailed biological explanation, consequences, and actionable ancient remedy.",
    "cta": "Call to action to follow for daily gut health secrets."
  }},
  "cards": {{
    "warning_title": "The Fatal Mistake: Iced Drinks With Meals",
    "warning_subtitle": "Cold liquids extinguish digestive fire, solidifying dietary fats and trapping toxins in the gut.",
    "remedy_title": "The Ancient Fix: Sip Warm Liquids",
    "remedy_subtitle": "Drink warm water or ginger tea with meals to ignite gastric enzymes and eliminate bloating."
  }}
}}"""


def generate_video_assets(
    topic_data: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
    use_mock_on_offline: bool = True,
) -> Dict[str, Any]:
    """Generates script, audio, subtitles, and stock videos for a topic."""
    current_dir = Path(__file__).resolve().parent
    work_dir = (output_dir or (current_dir / "output" / str(uuid.uuid4())[:8])).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Topic & Audience Feedback Directives
    optimizer = FeedbackOptimizer()
    feedback = optimizer.analyze_feedback()
    directive = feedback.get("prompt_directive", "")

    selected_topic = topic_data or pick_random_topic(category_key=feedback.get("top_category"))
    logger.info(f"[*] Selected Topic: '{selected_topic['subject']}' (Category: {selected_topic['category_title']})")

    # 2. Query Ollama with Feedback Directives
    system_prompt = build_system_prompt_with_feedback(directive)
    user_prompt = (
        f"Write a viral 45-55 second video script (115-135 words) about:\n"
        f"Subject: {selected_topic['subject']}\n"
        f"Key Fact: {selected_topic['key_fact']}\n"
        f"Body Element: {selected_topic.get('dosha', 'Digestive Balance')}\n"
        f"CRITICAL: Translate all Sanskrit concepts (Agni, Ama, Dosha) into clear English so Western viewers immediately understand."
    )

    try:
        script_json = query_ollama_json(prompt=user_prompt, system=system_prompt)
    except Exception as e:
        if not use_mock_on_offline:
            raise
        logger.warning(f"Ollama unavailable ({e}). Using comprehensive catalog-guided fallback script for testing...")
        script_json = {
            "topic": selected_topic["subject"],
            "category": selected_topic["category_title"],
            "visual_search_queries": selected_topic.get("keywords") or [
                "glass ice water pouring",
                "stomach digestion gut anatomy",
                "drinking cold water table",
                "bloated stomach pain belly",
                "fermentation gut health",
                "pouring hot steaming herbal tea",
                "fresh ginger root slicing kitchen",
                "healthy energetic smiling person",
            ],
            "english_script": {
                "hook": f"Stop drinking ice-cold water with your meals! You are unknowingly shutting down your body's digestive power.",
                "body": (
                    "In ancient health science, your stomach breaks down food using an internal metabolic heat known as digestive fire. "
                    "When you drink ice-cold water while eating, you instantly extinguish this digestive fire, freezing your stomach enzymes. "
                    "This forces dietary fats to solidify and congeal, halting digestion. Undigested food then sits and ferments in your intestines, "
                    "accumulating into toxic metabolic sludge that causes severe bloating, gas, brain fog, and chronic fatigue. "
                    "Instead, follow the golden rule: drink warm water or sip fresh ginger tea with your meals. "
                    "Warm liquids ignite your digestive enzymes, melt fats smoothly, and keep your gut feeling light and energized."
                ),
                "cta": "Follow for daily holistic gut health secrets to heal your body naturally!",
            },
            "cards": {
                "warning_title": "The Fatal Mistake: Iced Drinks With Meals",
                "warning_subtitle": "Ice-cold water extinguishes digestive fire, congealing fats and fermenting toxic waste in the gut.",
                "remedy_title": "The Ancient Fix: Sip Warm Liquids",
                "remedy_subtitle": "Drink warm water or ginger tea with meals to stimulate digestive enzymes and eliminate bloating.",
            },
        }

    # 3. Synthesize Speech Audio (Kokoro TTS / Edge-TTS)
    eng_script = script_json.get("english_script", {})
    combined_text = f"{eng_script.get('hook', '')} {eng_script.get('body', '')} {eng_script.get('cta', '')}".strip()

    raw_voice_path = work_dir / "voiceover_raw.wav"
    mastered_audio_path = work_dir / "voiceover_master.wav"
    try:
        synthesize_with_kokoro(
            text=combined_text,
            output_path=raw_voice_path,
            voice="af_heart",
            lang_code="a",
        )
    except Exception as tts_err:
        logger.warning(f"Kokoro TTS offline ({tts_err}). Falling back to Edge-TTS...")
        synthesize_with_edge(text=combined_text, output_path=raw_voice_path)

    # Master audio with deep 432Hz ambient frequency bed (-22dB) for documentary feel
    try:
        master_voice_with_ambient(voice_wav=raw_voice_path, output_wav=mastered_audio_path, ambient_db=-22.0)
    except Exception as master_err:
        logger.warning(f"Audio mastering fallback to raw: {master_err}")
        mastered_audio_path = raw_voice_path

    # 4. Generate Word-Level Subtitles via Whisper
    subtitles_path = work_dir / "subtitles.json"
    whisper_result = transcribe_audio_words(audio_path=mastered_audio_path, output_json_path=subtitles_path)

    # Flatten word timestamps for Remotion
    words_list: List[Dict[str, Any]] = []
    for segment in whisper_result.get("segments", []):
        for w in segment.get("words", []):
            word_str = w.get("word", "").strip()
            if word_str:
                words_list.append({
                    "word": word_str,
                    "start": round(float(w.get("start", 0.0)), 2),
                    "end": round(float(w.get("end", 0.0)), 2),
                })

    # 5. Fetch Visual Footage Matching Chronological Narrative Beats
    stock_queries = script_json.get("visual_search_queries") or selected_topic.get("keywords") or [
        "glass ice water pouring",
        "stomach digestion gut anatomy",
        "drinking cold water table",
        "bloated stomach pain belly",
        "pouring hot steaming herbal tea",
        "fresh ginger root slicing kitchen",
    ]
    stock_clips_dir = work_dir / "clips"
    downloaded_clips = download_batch_stock_videos(queries=stock_queries, output_dir=stock_clips_dir)

    segments = whisper_result.get("segments", [])
    duration_sec = float(segments[-1].get("end", 45.0)) if segments else 45.0
    fps = 30

    # 6. Construct Frame-Synchronized Visual Scenes
    # Maps each downloaded clip directly to spoken sentence segments so cuts are time-accurate
    scenes: List[Dict[str, Any]] = []
    num_clips = len(downloaded_clips)
    if num_clips > 0 and segments:
        clip_idx = 0
        current_scene_start = 0.0

        for s_idx, seg in enumerate(segments):
            seg_end = float(seg.get("end", 0.0))
            seg_dur = seg_end - current_scene_start
            is_last = (s_idx == len(segments) - 1)

            # Cut scene on natural sentence boundary when duration reaches >= 4.0s (or on last segment)
            if seg_dur >= 4.0 or is_last:
                start_f = int(current_scene_start * fps)
                end_f = int(seg_end * fps)
                dur_f = max(fps * 2, end_f - start_f)
                assigned_clip = downloaded_clips[clip_idx % num_clips]

                scenes.append({
                    "clip": str(assigned_clip),
                    "startFrame": start_f,
                    "durationFrames": dur_f,
                })
                clip_idx += 1
                current_scene_start = seg_end
    elif num_clips > 0:
        # Fallback if Whisper returned no segments: divide evenly
        frames_per = int(duration_sec * fps / num_clips)
        for idx, clip in enumerate(downloaded_clips):
            scenes.append({
                "clip": str(clip),
                "startFrame": idx * frames_per,
                "durationFrames": frames_per,
            })

    # 7. Construct Educational Infographic Cards with Complete, Untruncated Text
    cards_data = script_json.get("cards", {})
    warning_title = cards_data.get("warning_title") or "The Fatal Mistake: Iced Drinks With Meals"
    warning_sub = cards_data.get("warning_subtitle") or "Ice-cold water extinguishes digestive fire, congealing fats and fermenting toxic waste in the gut."

    remedy_title = cards_data.get("remedy_title") or "The Ancient Fix: Sip Warm Liquids"
    remedy_sub = cards_data.get("remedy_subtitle") or "Drink warm water or ginger tea with meals to stimulate digestive enzymes and eliminate bloating."

    card_duration_frames = int(6.5 * fps)
    warning_start_frame = int(max(6.0, duration_sec * 0.18) * fps)
    remedy_start_frame = int(max(warning_start_frame / fps + 8.0, duration_sec * 0.62) * fps)

    cards = [
        {
            "type": "warning",
            "title": warning_title,
            "subtitle": warning_sub,
            "startFrame": warning_start_frame,
            "durationFrames": card_duration_frames,
        },
        {
            "type": "remedy",
            "title": remedy_title,
            "subtitle": remedy_sub,
            "startFrame": remedy_start_frame,
            "durationFrames": card_duration_frames,
        },
    ]

    return {
        "work_dir": work_dir,
        "topic": selected_topic,
        "script": script_json,
        "audio_path": mastered_audio_path,
        "subtitles_path": subtitles_path,
        "words": words_list,
        "scenes": scenes,
        "cards": cards,
        "stock_clips": [str(c) for c in downloaded_clips],
        "duration_sec": duration_sec,
    }


def render_remotion_video(
    assets: Dict[str, Any],
    output_mp4: Path,
) -> Optional[Path]:
    """Renders the video composited in React/Remotion with staged public assets."""
    renderer_dir = PROJECT_ROOT / "ayurveda-content" / "renderer"
    public_dir = renderer_dir / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    props_file = assets["work_dir"] / "remotion_props.json"
    session_id = str(uuid.uuid4())[:8]

    # Stage audio into renderer/public/ for zero-CORS browser access
    staged_audio_name = f"voice_{session_id}.wav"
    staged_audio_path = public_dir / staged_audio_name
    if assets.get("audio_path") and Path(assets["audio_path"]).exists() and Path(assets["audio_path"]).stat().st_size > 1000:
        shutil.copyfile(str(assets["audio_path"]), str(staged_audio_path))
    else:
        staged_audio_name = ""

    # Stage visual clips if any (preserve actual extension .mp4 / .jpg)
    staged_clips: List[str] = []
    clip_map: Dict[str, str] = {}
    for idx, clip in enumerate(assets.get("stock_clips", [])):
        clip_p = Path(clip)
        if clip_p.exists() and clip_p.stat().st_size > 10000:
            ext = clip_p.suffix.lower() if clip_p.suffix else ".mp4"
            c_name = f"clip_{session_id}_{idx}{ext}"
            shutil.copyfile(str(clip_p), str(public_dir / c_name))
            staged_clips.append(c_name)
            clip_map[str(clip)] = c_name
            clip_map[str(clip_p.resolve())] = c_name

    # Map frame-synced scenes to staged public filenames
    staged_scenes: List[Dict[str, Any]] = []
    for sc in assets.get("scenes", []):
        raw_clip = sc.get("clip", "")
        mapped_name = clip_map.get(raw_clip, "")
        if not mapped_name and staged_clips:
            mapped_name = staged_clips[0]
        if mapped_name:
            staged_scenes.append({
                "clip": mapped_name,
                "startFrame": sc["startFrame"],
                "durationFrames": sc["durationFrames"],
            })

    props = {
        "audioSrc": staged_audio_name,
        "words": assets["words"],
        "videoClips": staged_clips,
        "scenes": staged_scenes,
        "badgeText": assets["topic"].get("badge", "GUT HEALTH SECRETS"),
        "topicTitle": assets["topic"].get("subject", ""),
        "cards": assets.get("cards", []),
        "durationInSeconds": assets["duration_sec"],
    }

    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(props, f, indent=2)

    cmd = [
        "npx",
        "remotion",
        "render",
        "AyurvedaShort",
        str(output_mp4.resolve()),
        f"--props={str(props_file.resolve())}",
        "--public-dir=public",
    ]

    logger.info(f"Triggering Remotion render: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(renderer_dir), capture_output=True, text=True)

    # Cleanup staged public files to keep renderer clean
    if staged_audio_path.exists():
        staged_audio_path.unlink()
    for c_name in staged_clips:
        cp = public_dir / c_name
        if cp.exists():
            cp.unlink()

    if result.returncode == 0 and output_mp4.exists():
        logger.info(f"[+] Successfully rendered final video: {output_mp4}")
        return output_mp4
    else:
        logger.error(f"Remotion render failed (code {result.returncode}):\n{result.stderr}\n{result.stdout}")
        return None


def run_ayurveda_pipeline(
    category_key: Optional[str] = None,
    publish: bool = False,
    dry_run_publish: bool = True,
) -> Dict[str, Any]:
    """Runs the complete end-to-end automated generation, rendering, and logging flow."""
    logger.info("=== Starting Ayurveda Video Pipeline ===")

    # Step 1 & 2: Select topic and generate assets
    topic_data = pick_random_topic(category_key=category_key)
    assets = generate_video_assets(topic_data=topic_data)

    # Step 3: Render Final 9:16 MP4
    output_video = assets["work_dir"] / "final_ayurveda_short.mp4"
    render_remotion_video(assets=assets, output_mp4=output_video)

    # Step 4: Log into Analytics Database
    db = AyurvedaAnalyticsDB()
    video_id = str(uuid.uuid4())[:12]
    titles = topic_data.get("titles", {})
    chosen_title = titles.get("variant_a_curiosity", topic_data["subject"])

    word_count = len(assets["words"])
    speech_wpm = round((word_count / max(1.0, assets["duration_sec"])) * 60, 1)

    record_data = {
        "video_id": video_id,
        "topic": topic_data["subject"],
        "category": topic_data["category_title"],
        "title": chosen_title,
        "title_variant": "curiosity",
        "hook_text": assets["script"].get("english_script", {}).get("hook", ""),
        "hook_style": "curiosity_gap",
        "duration_sec": assets["duration_sec"],
        "word_count": word_count,
        "speech_wpm": speech_wpm,
    }

    # Step 5: Multi-Platform Publishing
    if publish:
        logger.info(f"Publishing to YouTube, TikTok, and Instagram (dry_run={dry_run_publish})...")
        pub_results = publish_to_all_platforms(
            video_path=output_video,
            metadata={
                "title": chosen_title,
                "description": f"{assets['script'].get('english_script', {}).get('body', '')}\n\n#Ayurveda #Wellness #Health #Dosha #Shorts",
                "tags": ["Ayurveda", "Health", "DailyRoutine", "HolisticHealth", "Shorts"],
            },
            dry_run=dry_run_publish,
        )
        record_data["youtube_url"] = f"https://youtu.be/{pub_results.get('youtube')}" if pub_results.get("youtube") else ""

    db.record_new_video(record_data)
    logger.info(f"[+] Video logged to Analytics DB (ID: {video_id})")

    return {
        "video_id": video_id,
        "output_video": output_video,
        "topic": topic_data["subject"],
        "duration": assets["duration_sec"],
        "record": record_data,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ayurveda Content Automation Pipeline")
    parser.add_argument("--category", type=str, default=None, help="Optional category key")
    parser.add_argument("--publish", action="store_true", help="Publish video to social platforms")
    parser.add_argument("--live", action="store_true", help="Perform real publish (otherwise dry-run)")
    args = parser.parse_args()

    run_ayurveda_pipeline(
        category_key=args.category,
        publish=args.publish,
        dry_run_publish=not args.live,
    )
