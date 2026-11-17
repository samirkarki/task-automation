#!/usr/bin/env python3
"""
Professional Theatrical Sound Director & Pristine Audio Mastering Engine
Produces broadcast-grade, serene documentary audio:
  - Lead: Studio-quality neural voiceover (-1.0 dB True Peak, crystal-clear presence)
  - Bed: Warm 432Hz harmonic healing frequency / acoustic meditation drone (-24 dB)
  - Transition Accent: Exactly ONE subtle, gentle harmonic bell at the Remedy revelation beat
  - Zero digital clipping, zero harsh saturation, zero white-noise static, zero cut whooshes
"""

import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import numpy as np
import soundfile as sf

logger = logging.getLogger("common.sound_director")


class HarmonicSoundSynthesizer:
    """
    Synthesizes pure, organic harmonic tones using pure sine wave modal synthesis.
    Strictly avoids random white-noise to prevent any harsh hiss, static, or distortion.
    """

    @staticmethod
    def synth_healing_chime(duration_sec: float = 3.0, sr: int = 24000) -> np.ndarray:
        """
        Synthesizes a crystalline 528Hz Solfeggio / Tibetan singing bowl chime.
        Pure harmonic partials with natural exponential decay.
        """
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

        # 528Hz root (Transformation & DNA repair harmonic) + clean overtones
        partials = [
            (528.0, 0.50, 1.2),   # Root
            (1056.0, 0.28, 1.8),  # 2nd harmonic
            (1584.0, 0.14, 2.4),  # 3rd harmonic
            (2112.0, 0.06, 3.2),  # 4th harmonic
            (264.0, 0.20, 0.9),   # Sub-octave warmth
        ]

        audio = np.zeros(n_samples, dtype=np.float32)
        for freq, amp, decay in partials:
            env = np.exp(-t * decay) * np.clip(t / 0.012, 0.0, 1.0)
            audio += amp * np.sin(2 * np.pi * freq * t) * env

        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_warm_singing_bowl(duration_sec: float = 4.0, sr: int = 24000) -> np.ndarray:
        """
        Synthesizes a resonant bronze Tibetan singing bowl tone (216Hz grounding frequency).
        Features gentle modal beating and velvety organic sustain.
        """
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

        # Warm dual-tone beating (216Hz and 218Hz create a gentle 2Hz binaural prana pulse)
        b1 = 0.50 * np.sin(2 * np.pi * 216.0 * t)
        b2 = 0.40 * np.sin(2 * np.pi * 218.0 * t)
        b3 = 0.20 * np.sin(2 * np.pi * 432.0 * t)
        b4 = 0.10 * np.sin(2 * np.pi * 648.0 * t)

        env = np.exp(-t * 0.75) * np.clip(t / 0.03, 0.0, 1.0)
        audio = (b1 + b2 + b3 + b4) * env
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)


class SoundDirector:
    """
    Automated Professional Theatrical Sound Director.
    Creates an immersive, tranquil, broadcast-grade soundtrack:
      - Voiceover clarity is prioritized above all else (normalized to -1.0 dB true peak)
      - Continuous soothing 432Hz ambient meditation sound bed (-24 dB)
      - Exactly ONE organic harmonic chime at the revelation/remedy transition
      - ZERO cut whooshes, ZERO static/white-noise, ZERO digital distortion
    """

    def __init__(self, sfx_dir: Optional[Path] = None):
        self.sfx_dir = sfx_dir or (Path(__file__).parent / "sfx_soundpack")
        self.sfx_dir.mkdir(parents=True, exist_ok=True)
        self.synth = HarmonicSoundSynthesizer()
        self._ensure_default_soundpack()

    def _ensure_default_soundpack(self, sr: int = 24000):
        """Pre-renders default pure harmonic audio stems to disk if missing."""
        default_stems = {
            "healing_chime.wav": self.synth.synth_healing_chime(3.0, sr),
            "singing_bowl.wav": self.synth.synth_warm_singing_bowl(4.0, sr),
        }
        for fname, data in default_stems.items():
            fpath = self.sfx_dir / fname
            if not fpath.exists() or fpath.stat().st_size < 100:
                sf.write(str(fpath), data.astype(np.float32), sr)

    def load_stem(self, stem_name: str, target_sr: int = 24000) -> np.ndarray:
        """Loads a pure harmonic stem from disk or synthesizes on the fly."""
        fpath = self.sfx_dir / f"{stem_name}.wav" if not stem_name.endswith(".wav") else self.sfx_dir / stem_name
        if fpath.exists() and fpath.stat().st_size > 100:
            try:
                data, sr = sf.read(str(fpath), dtype="float32")
                if len(data.shape) > 1:
                    data = data[:, 0]
                if sr != target_sr:
                    from scipy.signal import resample
                    n_out = int(len(data) * float(target_sr) / float(sr))
                    data = resample(data, n_out).astype(np.float32)
                return data
            except Exception as e:
                logger.debug(f"Could not read {fpath}: {e}")

        if "bowl" in stem_name.lower():
            return self.synth.synth_warm_singing_bowl(sr=target_sr)
        return self.synth.synth_healing_chime(sr=target_sr)

    def build_theatrical_soundtrack(
        self,
        voice_path: Union[str, Path],
        output_path: Union[str, Path],
        shot_definitions: Optional[List[Dict[str, Any]]] = None,
        ambient_drone_db: float = -24.0,
        remedy_accent_db: float = -14.0,
    ) -> Path:
        """
        Mixes a pristine, peaceful, broadcast-standard audio master:
          Track 1: Studio Voiceover (Normalized to -1.0 dB True Peak, crystal-clear presence)
          Track 2: Ambient 432Hz Healing Frequency Bed (-24.0 dB, calm continuous prana)
          Track 3: Exactly ONE subtle harmonic singing bowl/chime at the Remedy transition point (-14 dB)
          Mastering: Clean linear headroom scaling (Peak capped at -0.5 dB, zero saturation clipping)
        """
        v_path = Path(voice_path).resolve()
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        voice_data, sr = sf.read(str(v_path), dtype="float32")
        if len(voice_data.shape) > 1:
            voice_data = voice_data[:, 0]  # Mono

        total_samples = len(voice_data)
        total_sec = total_samples / float(sr)

        # 1. Studio Voiceover True Peak Normalization (-1.0 dBFS = 0.891)
        v_max = np.max(np.abs(voice_data))
        if v_max > 0.001:
            voice_norm = (voice_data / v_max) * 0.891
        else:
            voice_norm = voice_data

        # 2. Continuous 432Hz Ambient Healing Sound Bed (-24 dB)
        from common.audio_mastering import generate_ayurveda_ambient_bed
        temp_ambient = out_p.parent / f"temp_ambient_{out_p.stem}.wav"
        generate_ayurveda_ambient_bed(total_sec, temp_ambient, sample_rate=sr, target_db=ambient_drone_db)
        ambient_data, _ = sf.read(str(temp_ambient), dtype="float32")
        if len(ambient_data.shape) > 1:
            ambient_data = ambient_data[:, 0]
        if temp_ambient.exists():
            temp_ambient.unlink()

        amb_len = min(total_samples, len(ambient_data))
        ambient_track = np.zeros(total_samples, dtype=np.float32)
        ambient_track[:amb_len] = ambient_data[:amb_len]

        # 3. Exactly ONE Organic Harmonic Accent at the Remedy Transition
        # Identify the pivotal shot where the narrative shifts from Danger/Mistake to Remedy
        accent_track = np.zeros(total_samples, dtype=np.float32)
        remedy_start_sec: Optional[float] = None

        if shot_definitions:
            for shot in shot_definitions:
                role = str(shot.get("role", "")).lower()
                text = str(shot.get("sentence_text", "")).lower()
                if any(w in role or w in text for w in ["remedy", "fix", "solution", "instead", "add warming", "support"]):
                    remedy_start_sec = float(shot.get("start_sec", 0.0))
                    break

        if remedy_start_sec is None:
            # Default to ~55% into the video where the solution naturally begins
            remedy_start_sec = total_sec * 0.55

        start_idx = int(remedy_start_sec * sr)
        if 0 < start_idx < total_samples:
            chime_stem = self.load_stem("singing_bowl.wav", target_sr=sr)
            chime_gain = 10.0 ** (remedy_accent_db / 20.0)
            c_len = min(len(chime_stem), total_samples - start_idx)
            if c_len > 0:
                accent_track[start_idx : start_idx + c_len] = chime_stem[:c_len] * chime_gain
                logger.info(f"[+] Placed single organic remedy chime at {remedy_start_sec:.1f}s ({remedy_accent_db}dB).")

        # 4. Clean Linear Mastering with True Peak Headroom Control (NO tanh clipping!)
        # Voice (0.891) + Ambient (scaled) + Accent
        summed = voice_norm + ambient_track + accent_track

        # Peak Ceiling Limiter: ensure peak does not exceed -0.5 dBFS (0.944)
        peak = np.max(np.abs(summed))
        if peak > 0.944:
            headroom_scale = 0.944 / peak
            mastered = summed * headroom_scale
            logger.info(f"[Mastering] Applied gentle linear headroom scaling: {headroom_scale:.3f} (peak was {peak:.2f})")
        else:
            mastered = summed

        sf.write(str(out_p), mastered.astype(np.float32), sr)
        logger.info(f"[+] Broadcast-grade audio mastered cleanly: {out_p.name} ({total_sec:.1f}s, Peak: {np.max(np.abs(mastered)):.2f})")
        return out_p


def test_sound_director() -> bool:
    """Verifies that the serene sound director mixes audio cleanly without distortion."""
    director = SoundDirector()
    test_shots = [
        {"start_sec": 0.0, "role": "The Warning"},
        {"start_sec": 4.0, "role": "The Science"},
        {"start_sec": 8.0, "role": "The Ancient Fix: Warm Digestion"},
        {"start_sec": 12.0, "role": "Radiant Vitality"},
    ]

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        dummy_voice = tmp_p / "dummy_voice.wav"
        out_master = tmp_p / "mastered.wav"

        sr = 24000
        t = np.linspace(0, 16.0, int(16.0 * sr), endpoint=False, dtype=np.float32)
        v_data = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        sf.write(str(dummy_voice), v_data, sr)

        res = director.build_theatrical_soundtrack(dummy_voice, out_master, test_shots)
        if res.exists() and res.stat().st_size > 1000:
            data, _ = sf.read(str(res))
            peak = np.max(np.abs(data))
            assert peak <= 0.95, f"Audio peaked above safe limit: {peak}"
            print(f"[+] SoundDirector test passed! Mastered audio peak: {peak:.3f}")
            return True
    return False


if __name__ == "__main__":
    test_sound_director()
