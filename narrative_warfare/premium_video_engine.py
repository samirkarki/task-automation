#!/usr/bin/env python3
"""
Premium Video Generation Engine (narrative_warfare/premium_video_engine.py)
Autonomous production framework for the 'Narrative Psychology & Corporate Warfare' niche.

Pipeline Architecture:
1. Scripting: Ollama Qwen3-coder:30b -> Strictly Validated Structured JSON + 3-Round Auto-Correction
2. Voiceover: Kokoro-82M / F5-TTS / Edge-TTS Studio Narration -> 0dB Normalized Audio
3. Mastering: Vectorized Sub-Bass Drone (-20dB) + Voice (0dB) Mixdown with Soft Limiting
4. Subtitles: Faster-Whisper Base Model -> Millisecond Word Alignment & Speech Velocity Scaling
5. Compositing: MoviePy & Native FFmpeg -> 1080x1920 (9:16) Kinetic Video with Ken Burns & Dynamic Vignette
6. Disclosure: Automated alteredContent: true compliance for YouTube Data API & TikTok Webhooks
"""

import os
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from narrative_warfare.script_controller import (
    NarrativeScript,
    generate_narrative_script,
    DEFAULT_MODEL as DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
)
from narrative_warfare.voiceover_studio import (
    generate_studio_voiceover,
    DEFAULT_KOKORO_VOICE,
)
from narrative_warfare.audio_mastering import (
    master_audio_composite,
)
from narrative_warfare.whisper_transcriber import (
    generate_kinetic_subtitles,
    SubtitleCard,
)
from narrative_warfare.kinetic_compositor import (
    render_kinetic_short_video,
    DEFAULT_FPS,
)
from narrative_warfare.platform_disclosure import (
    build_compliant_youtube_payload,
    build_compliant_tiktok_payload,
    upload_to_youtube_with_disclosure,
)

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("premium_video_engine")

OUTPUT_BASE_DIR = PROJECT_ROOT / "narrative_warfare" / "output"
DEFAULT_RCLONE_REMOTE = os.getenv(
    "RCLONE_WARFARE_REMOTE",
    "gdrive:TaskAutomation/narrative-warfare/",
)


# -----------------------------------------------------------------------------
# Google Drive Synchronization (rclone)
# -----------------------------------------------------------------------------
def sync_session_to_remote(
    session_dir: Path,
    remote_destination: str = DEFAULT_RCLONE_REMOTE,
    purge_local: bool = False,
) -> bool:
    """
    Syncs session assets (video, audio, manifests) to Google Drive via rclone.
    Mirrors the cloud backup workflow used in faceless_content.
    """
    if not shutil.which("rclone"):
        logger.warning("[RCLONE] rclone binary is not found on system PATH. Skipping Google Drive upload.")
        return False

    target_remote = f"{remote_destination.rstrip('/')}/{session_dir.name}"
    logger.info(f"[RCLONE] Syncing session directory '{session_dir.name}' to '{target_remote}'...")
    try:
        cmd = ["rclone", "copy", str(session_dir), target_remote]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        logger.info(f"[RCLONE] Successfully synced session to Google Drive: {target_remote}")

        if purge_local:
            logger.info(f"[RCLONE] Purging local files in {session_dir} to conserve disk space...")
            shutil.rmtree(session_dir)

        return True
    except subprocess.CalledProcessError as cpe:
        logger.error(f"[RCLONE ERROR] rclone failed: {cpe.stderr}")
        return False
    except Exception as e:
        logger.error(f"[RCLONE ERROR] Exception during Google Drive sync: {e}")
        return False


# -----------------------------------------------------------------------------
# Pipeline Execution Controller
# -----------------------------------------------------------------------------
class PremiumVideoPipeline:
    def __init__(
        self,
        topic: Optional[str] = None,
        model: str = DEFAULT_OLLAMA_MODEL,
        voice: str = DEFAULT_KOKORO_VOICE,
        seed: Optional[int] = None,
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
        skip_youtube: bool = False,
        skip_rclone: bool = False,
        purge_local: bool = False,
        remote_dest: Optional[str] = None,
        keep_staging: bool = False,
    ):
        self.topic = topic
        self.model = model
        self.voice = voice
        self.seed = seed
        self.dry_run = dry_run
        self.skip_youtube = skip_youtube
        self.skip_rclone = skip_rclone
        self.purge_local = purge_local
        self.remote_dest = remote_dest or DEFAULT_RCLONE_REMOTE
        self.keep_staging = keep_staging

        # Initialize unique session run folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = (output_dir or OUTPUT_BASE_DIR) / f"run_{timestamp}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.manifest: Dict[str, Any] = {
            "session_id": f"warfare_run_{timestamp}",
            "started_at": datetime.now().isoformat(),
            "topic_request": topic,
            "model": model,
            "voice": voice,
            "stages": {},
        }

    def execute(self) -> Dict[str, Any]:
        """
        Executes complete production pipeline end-to-end with strict validation,
        file handovers, and platform policy disclosures.
        """
        logger.info("=================================================================")
        logger.info("Starting Premium Video Production Pipeline: Narrative Warfare")
        logger.info(f"Session Output Directory: {self.run_dir}")
        logger.info("=================================================================")

        try:
            # -----------------------------------------------------------------
            # Stage 1: Scripting Backend (Ollama Qwen3-coder:30b)
            # -----------------------------------------------------------------
            logger.info("\n--- [STAGE 1/6] Scripting & Psychological Structuring ---")
            script: NarrativeScript = generate_narrative_script(
                topic=self.topic,
                model=self.model,
            )
            if self.seed:
                script.visual_style_seed = self.seed

            # Persist script manifest
            script_path = self.run_dir / "script_manifest.json"
            with open(script_path, "w", encoding="utf-8") as f:
                json.dump(script.to_dict(), f, indent=2)

            self.manifest["stages"]["stage1_script"] = {
                "status": "COMPLETED",
                "topic": script.topic,
                "visual_style_seed": script.visual_style_seed,
                "hook": script.psychological_hook,
                "manifest_file": str(script_path),
            }
            logger.info(f"Script validated: '{script.topic}' (Seed={script.visual_style_seed})")

            # -----------------------------------------------------------------
            # Stage 2: Studio Voiceover Synthesis (Kokoro-82M / Fallback)
            # -----------------------------------------------------------------
            logger.info("\n--- [STAGE 2/6] Studio Voiceover Synthesis ---")
            raw_voice_wav = self.run_dir / "voiceover_0db.wav"
            spoken_text = script.full_spoken_text
            generate_studio_voiceover(spoken_text, raw_voice_wav, voice=self.voice)

            self.manifest["stages"]["stage2_voiceover"] = {
                "status": "COMPLETED",
                "voice_file": str(raw_voice_wav),
                "file_size_bytes": raw_voice_wav.stat().st_size,
            }

            # -----------------------------------------------------------------
            # Stage 3: Audio Mastering (0dB Voice + -20dB Ambient Drone)
            # -----------------------------------------------------------------
            logger.info("\n--- [STAGE 3/6] Dynamic Acoustic Mastering ---")
            master_audio_wav = self.run_dir / "master_audio_bed.wav"
            master_audio_composite(raw_voice_wav, master_audio_wav, drone_db=-20.0)

            self.manifest["stages"]["stage3_audio_master"] = {
                "status": "COMPLETED",
                "master_audio_file": str(master_audio_wav),
                "voice_spec": "0dB Normalized",
                "drone_spec": "-20dB Sub-Bass Pulse Hard-Capped",
            }

            # -----------------------------------------------------------------
            # Stage 4: Word-Level Transcription & Speech Velocity (Faster-Whisper)
            # -----------------------------------------------------------------
            logger.info("\n--- [STAGE 4/6] Faster-Whisper Word-Level Kinetic Tracking ---")
            subtitle_cards: List[SubtitleCard] = generate_kinetic_subtitles(
                raw_voice_wav,
                spoken_text,
                emphasis_keywords=script.caption_emphasis_keywords,
            )

            # Estimate hook duration from subtitle card timestamps
            hook_words = set(script.psychological_hook.lower().split())
            hook_duration = 3.5
            for card in subtitle_cards:
                card_words = set(card.text.lower().split())
                if card_words.issubset(hook_words) or len(card_words.intersection(hook_words)) >= len(card_words) * 0.7:
                    hook_duration = max(hook_duration, card.end)

            subtitles_manifest = self.run_dir / "kinetic_subtitles.json"
            with open(subtitles_manifest, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "text": c.text,
                        "start": c.start,
                        "end": c.end,
                        "velocity_scale": c.velocity_scale,
                        "has_emphasis": c.has_emphasis,
                    }
                    for c in subtitle_cards
                ], f, indent=2)

            self.manifest["stages"]["stage4_transcription"] = {
                "status": "COMPLETED",
                "card_count": len(subtitle_cards),
                "calculated_hook_duration_sec": hook_duration,
                "subtitles_file": str(subtitles_manifest),
            }

            # -----------------------------------------------------------------
            # Stage 5: Media Compositing Pipeline (MoviePy & FFmpeg)
            # -----------------------------------------------------------------
            logger.info("\n--- [STAGE 5/6] 1080x1920 (9:16) Kinetic Video Compositing ---")
            final_mp4 = self.run_dir / "final_short_9x16.mp4"

            if self.dry_run:
                logger.info("[DRY-RUN] Skipping full frame rendering. Writing mock MP4 placeholder.")
                final_mp4.touch()
            else:
                render_kinetic_short_video(
                    master_audio_path=master_audio_wav,
                    subtitle_cards=subtitle_cards,
                    output_video_path=final_mp4,
                    topic=script.topic,
                    visual_seed=script.visual_style_seed,
                    hook_duration=hook_duration,
                    spoken_text=spoken_text,
                    fps=DEFAULT_FPS,
                )

            self.manifest["stages"]["stage5_compositing"] = {
                "status": "COMPLETED",
                "video_file": str(final_mp4),
                "dimensions": "1080x1920",
                "aspect_ratio": "9:16",
                "fps": DEFAULT_FPS,
            }

            # -----------------------------------------------------------------
            # Stage 6: Platform Policy Disclosure & Distribution
            # -----------------------------------------------------------------
            logger.info("\n--- [STAGE 6/6] Platform Policy Compliance & Disclosure ---")
            yt_payload = build_compliant_youtube_payload(
                topic=script.topic,
                psychological_hook=script.psychological_hook,
            )
            tt_payload = build_compliant_tiktok_payload(
                topic=script.topic,
                video_path=final_mp4,
                hook_text=script.psychological_hook,
            )

            # Persist disclosure payloads for auditing
            payload_file = self.run_dir / "policy_disclosure_payload.json"
            with open(payload_file, "w", encoding="utf-8") as f:
                json.dump({"youtube": yt_payload, "tiktok": tt_payload}, f, indent=2)

            if self.skip_youtube:
                logger.info("[SKIP-YOUTUBE] Skipping live YouTube upload by user flag. Compliance metadata verified and saved.")
                upload_result = "SKIPPED_BY_FLAG"
            else:
                upload_result = upload_to_youtube_with_disclosure(
                    video_path=final_mp4,
                    topic=script.topic,
                    hook=script.psychological_hook,
                    dry_run=True if self.dry_run else False,
                )

            self.manifest["stages"]["stage6_disclosure"] = {
                "status": "COMPLETED",
                "youtube_altered_content_disclosed": True,
                "tiktok_ai_generated_disclosed": True,
                "upload_result": upload_result,
                "payload_file": str(payload_file),
            }

            # -----------------------------------------------------------------
            # Stage 7: Google Drive Remote Cloud Sync (rclone)
            # -----------------------------------------------------------------
            if not self.skip_rclone and not self.dry_run:
                logger.info("\n--- [STAGE 7/7] Google Drive Cloud Synchronization ---")
                synced = sync_session_to_remote(
                    session_dir=self.run_dir,
                    remote_destination=self.remote_dest,
                    purge_local=self.purge_local,
                )
                self.manifest["stages"]["stage7_rclone_sync"] = {
                    "status": "COMPLETED" if synced else "SKIPPED_OR_FAILED",
                    "remote_destination": self.remote_dest,
                    "synced": synced,
                }
            else:
                logger.info("\n[SKIP-RCLONE] Skipping Google Drive sync (flag set or dry-run). Assets preserved locally.")
                self.manifest["stages"]["stage7_rclone_sync"] = {
                    "status": "SKIPPED",
                    "reason": "dry_run" if self.dry_run else "user_flag",
                }

            # Clean temporary staging files if not requested to keep staging
            if not self.keep_staging and not self.dry_run:
                temp_files = list(self.run_dir.glob("temp_*"))
                for tf in temp_files:
                    try:
                        tf.unlink()
                    except Exception:
                        pass

            self.manifest["status"] = "SUCCESS"
            self.manifest["completed_at"] = datetime.now().isoformat()
            self.manifest["final_asset"] = str(final_mp4)

            logger.info("=================================================================")
            logger.info("Pipeline Execution Completed Successfully!")
            logger.info(f"Final 9:16 Video Asset: {final_mp4}")
            if not self.skip_rclone and not self.dry_run:
                logger.info(f"Google Drive Backup: {self.remote_dest.rstrip('/')}/{self.run_dir.name}")
            logger.info("=================================================================")

        except Exception as e:
            logger.error(f"Pipeline encountered critical failure: {e}", exc_info=True)
            self.manifest["status"] = "FAILED"
            self.manifest["error"] = str(e)
            raise
        finally:
            # Persist run manifest
            manifest_path = self.run_dir / "run_state.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2)
            logger.info(f"Session state saved at: {manifest_path}")

        return self.manifest


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Premium Video Engine: Autonomous 9:16 Media Production for Narrative Psychology & Corporate Warfare"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Corporate warfare / behavioral anomaly topic (e.g., 'The Steve Jobs Coup').",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_OLLAMA_MODEL,
        help=f"Ollama LLM model name (default: {DEFAULT_OLLAMA_MODEL}).",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=DEFAULT_KOKORO_VOICE,
        help=f"Studio voice identity (default: {DEFAULT_KOKORO_VOICE}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="4-digit visual style seed for deterministic color grading and vignette.",
    )
    parser.add_argument(
        "--remote",
        type=str,
        default=DEFAULT_RCLONE_REMOTE,
        help=f"rclone Google Drive destination remote (default: {DEFAULT_RCLONE_REMOTE}).",
    )
    parser.add_argument(
        "--skip-rclone",
        action="store_true",
        help="Skip automatic rclone sync to Google Drive.",
    )
    parser.add_argument(
        "--purge-local",
        action="store_true",
        help="Purge local video and audio files after successful Google Drive upload to save server disk.",
    )
    parser.add_argument(
        "--skip-youtube",
        "--skip-upload",
        action="store_true",
        dest="skip_youtube",
        help="Render the full video and generate policy disclosures, but skip live YouTube upload.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute pipeline stages and validate payloads without heavy video encoding.",
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Preserve intermediate audio and temporary frame files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Custom root directory for rendering outputs.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    pipeline = PremiumVideoPipeline(
        topic=args.topic,
        model=args.model,
        voice=args.voice,
        seed=args.seed,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        skip_youtube=args.skip_youtube,
        skip_rclone=args.skip_rclone,
        purge_local=args.purge_local,
        remote_dest=args.remote,
        keep_staging=args.keep_staging,
    )
    result = pipeline.execute()
    print("\nExecution Manifest Summary:")
    print(json.dumps({
        "status": result.get("status"),
        "topic": result.get("stages", {}).get("stage1_script", {}).get("topic"),
        "final_asset": result.get("final_asset"),
    }, indent=2))


if __name__ == "__main__":
    main()
