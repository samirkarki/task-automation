#!/usr/bin/env python3
"""
Theatrical Foley & Cinematic Sound Design Engine
Generates and mixes synchronized Foley sound effects (liquid pours, ice clinks, steam hisses)
and cinematic transitions (whooshes, risers, sub-bass impacts) with voiceover and ambient music.
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


class FoleySynthesizer:
    """
    High-fidelity physical/modal Foley audio synthesizer using NumPy.
    Synthesizes broadcast-grade sound effects without external sample dependencies.
    """

    @staticmethod
    def synth_ice_clink(duration_sec: float = 0.8, sr: int = 24000) -> np.ndarray:
        """Synthesizes high-Q crystalline resonant ice clink with secondary impact."""
        t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False, dtype=np.float32)
        # Primary impact (2850Hz, 4120Hz, 6300Hz)
        env1 = np.exp(-t * 28.0)
        clink1 = (
            0.50 * np.sin(2 * np.pi * 2850 * t)
            + 0.35 * np.sin(2 * np.pi * 4120 * t)
            + 0.15 * np.sin(2 * np.pi * 6300 * t)
        ) * env1

        # Secondary micro-bounce impact after 45ms (3100Hz, 4900Hz)
        delay = int(0.045 * sr)
        clink2 = np.zeros_like(clink1)
        if len(t) > delay:
            t2 = t[:-delay]
            env2 = np.exp(-t2 * 34.0) * 0.45
            clink2[delay:] = (
                0.60 * np.sin(2 * np.pi * 3100 * t2)
                + 0.40 * np.sin(2 * np.pi * 4900 * t2)
            ) * env2

        audio = clink1 + clink2
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_cold_water_splash(duration_sec: float = 1.2, sr: int = 24000) -> np.ndarray:
        """Synthesizes cold water turbulent splash and liquid bubble resonance."""
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
        noise = np.random.normal(0, 1, n_samples).astype(np.float32)

        # Bubble modal impulses
        bubbles = np.zeros(n_samples, dtype=np.float32)
        bubble_times = [0.05, 0.12, 0.22, 0.35, 0.48, 0.65]
        for bt in bubble_times:
            idx = int(bt * sr)
            if idx < n_samples:
                dur = min(0.15, duration_sec - bt)
                n_b = int(dur * sr)
                t_b = np.linspace(0, dur, n_b, endpoint=False)
                # Pitch sweep upwards (air cavity resonance)
                freq = 700.0 + 800.0 * (t_b / dur)
                b_env = np.sin(np.pi * (t_b / dur)) ** 2
                bubbles[idx : idx + n_b] += 0.4 * np.sin(2 * np.pi * freq * t_b) * b_env

        # Liquid envelope
        env = np.exp(-t * 3.5) * (1.0 - np.exp(-t * 40.0))
        audio = (noise * 0.45 + bubbles * 0.55) * env
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_brass_pour(duration_sec: float = 2.0, sr: int = 24000) -> np.ndarray:
        """Synthesizes steaming liquid pouring into a resonant metallic brass cup."""
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
        noise = np.random.normal(0, 1, n_samples).astype(np.float32)

        # Brass cavity acoustic modes (840Hz, 1680Hz, 2520Hz)
        brass_res = (
            0.40 * np.sin(2 * np.pi * 840 * t)
            + 0.25 * np.sin(2 * np.pi * 1680 * t)
            + 0.15 * np.sin(2 * np.pi * 2520 * t)
        )

        # Steady pour stream with gentle random turbulence
        envelope = np.clip(t / 0.3, 0.0, 1.0) * np.clip((duration_sec - t) / 0.4, 0.0, 1.0)
        lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 6.5 * t)
        audio = (noise * 0.65 + brass_res * 0.35) * envelope * lfo
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_steam_hiss(duration_sec: float = 1.8, sr: int = 24000) -> np.ndarray:
        """Synthesizes delicate rising thermal steam hissing gently."""
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
        noise = np.random.normal(0, 1, n_samples).astype(np.float32)

        # High frequency thermal drift
        envelope = np.sin(np.pi * (t / duration_sec)) ** 1.8
        lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 1.8 * t)
        audio = noise * envelope * lfo
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_cinematic_whoosh(duration_sec: float = 0.7, sr: int = 24000) -> np.ndarray:
        """Synthesizes a deep, velvety cinematic transition whoosh."""
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
        noise = np.random.normal(0, 1, n_samples).astype(np.float32)

        # Pitch swept bandpass effect
        freq = 120.0 + 800.0 * np.sin(np.pi * (t / duration_sec))
        sine_bed = 0.5 * np.sin(2 * np.pi * freq * t)

        envelope = np.sin(np.pi * (t / duration_sec)) ** 2
        audio = (noise * 0.4 + sine_bed * 0.6) * envelope
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_sub_bass_drop(duration_sec: float = 1.5, sr: int = 24000) -> np.ndarray:
        """Synthesizes a 45Hz sub-bass impact for dramatic cinematic warning hooks."""
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

        # Downward pitch bend from 80Hz -> 38Hz
        freq = 38.0 + 42.0 * np.exp(-t * 4.0)
        envelope = np.exp(-t * 2.2) * np.clip(t / 0.02, 0.0, 1.0)
        audio = np.sin(2 * np.pi * freq * t) * envelope
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)

    @staticmethod
    def synth_ethereal_chime(duration_sec: float = 2.5, sr: int = 24000) -> np.ndarray:
        """Synthesizes a crystalline 528Hz harmonic revelation chime for remedies."""
        n_samples = int(duration_sec * sr)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

        chime = (
            0.50 * np.sin(2 * np.pi * 528.0 * t)
            + 0.30 * np.sin(2 * np.pi * 1056.0 * t)
            + 0.15 * np.sin(2 * np.pi * 1584.0 * t)
            + 0.05 * np.sin(2 * np.pi * 2112.0 * t)
        )
        envelope = np.exp(-t * 1.4) * np.clip(t / 0.015, 0.0, 1.0)
        audio = chime * envelope
        max_val = np.max(np.abs(audio))
        return audio / (max_val + 1e-6)


class SoundDirector:
    """
    Automated Theatrical Sound Designer.
    Matches narrative beats and visual shot cuts to precision Foley sound effects,
    creating a rich 3D soundscape mixed with voiceover and harmonic healing drone.
    """

    def __init__(self, sfx_dir: Optional[Path] = None):
        self.sfx_dir = sfx_dir or (Path(__file__).parent / "sfx_soundpack")
        self.sfx_dir.mkdir(parents=True, exist_ok=True)
        self.synth = FoleySynthesizer()
        self._ensure_default_soundpack()

    def _ensure_default_soundpack(self, sr: int = 24000):
        """Pre-renders default broadcast SFX stems to disk if missing."""
        default_stems = {
            "ice_clink.wav": self.synth.synth_ice_clink(0.8, sr),
            "cold_water_splash.wav": self.synth.synth_cold_water_splash(1.2, sr),
            "brass_pour.wav": self.synth.synth_brass_pour(2.0, sr),
            "steam_hiss.wav": self.synth.synth_steam_hiss(1.8, sr),
            "whoosh_transition.wav": self.synth.synth_cinematic_whoosh(0.7, sr),
            "sub_bass_drop.wav": self.synth.synth_sub_bass_drop(1.5, sr),
            "ethereal_chime.wav": self.synth.synth_ethereal_chime(2.5, sr),
        }
        for fname, data in default_stems.items():
            fpath = self.sfx_dir / fname
            if not fpath.exists() or fpath.stat().st_size < 100:
                sf.write(str(fpath), data.astype(np.float32), sr)

    def load_sfx(self, sfx_name: str, target_sr: int = 24000) -> np.ndarray:
        """Loads SFX stem from soundpack or falls back to procedural synth."""
        fpath = self.sfx_dir / f"{sfx_name}.wav" if not sfx_name.endswith(".wav") else self.sfx_dir / sfx_name
        if fpath.exists() and fpath.stat().st_size > 100:
            try:
                data, sr = sf.read(str(fpath), dtype="float32")
                if len(data.shape) > 1:
                    data = data[:, 0]
                if sr != target_sr:
                    from scipy.signal import resample
                    n_samples = int(len(data) * target_sr / sr)
                    data = resample(data, n_samples).astype(np.float32)
                return data
            except Exception as e:
                logger.debug(f"Could not read SFX file {fpath.name}: {e}")

        # Procedural fallback
        stem = sfx_name.replace(".wav", "").lower()
        if "ice" in stem:
            return self.synth.synth_ice_clink(sr=target_sr)
        elif "pour" in stem or "water" in stem:
            return self.synth.synth_brass_pour(sr=target_sr)
        elif "steam" in stem:
            return self.synth.synth_steam_hiss(sr=target_sr)
        elif "sub" in stem or "drop" in stem:
            return self.synth.synth_sub_bass_drop(sr=target_sr)
        elif "chime" in stem or "bell" in stem:
            return self.synth.synth_ethereal_chime(sr=target_sr)
        return self.synth.synth_cinematic_whoosh(sr=target_sr)

    def build_theatrical_soundtrack(
        self,
        voice_path: Union[str, Path],
        output_path: Union[str, Path],
        shot_definitions: List[Dict[str, Any]],
        ambient_drone_db: float = -22.0,
        foley_db: float = -9.0,
        transition_whoosh_db: float = -11.0,
    ) -> Path:
        """
        Mixes multi-track broadcast-grade soundtrack:
          Track 1: Voiceover (0dB normalized peak, center-focused)
          Track 2: Foley SFX (placed at shot start or action trigger, -9dB)
          Track 3: Transition Whooshes (placed exactly at scene cuts, -11dB)
          Track 4: 432Hz ambient sound bed (-22dB) with soft-knee limiter.
        """
        v_path = Path(voice_path).resolve()
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        voice_data, sr = sf.read(str(v_path), dtype="float32")
        if len(voice_data.shape) > 1:
            voice_data = voice_data[:, 0]

        total_samples = len(voice_data)
        total_sec = total_samples / float(sr)

        # 1. 0dB Peak Normalize Voiceover
        v_max = np.max(np.abs(voice_data))
        voice_norm = (voice_data / (v_max + 1e-6)) * 0.95

        # 2. Multi-Track SFX & Foley Bus
        sfx_bus = np.zeros(total_samples, dtype=np.float32)
        whoosh_stem = self.load_sfx("whoosh_transition.wav", target_sr=sr)
        whoosh_gain = 10.0 ** (transition_whoosh_db / 20.0)

        for s_idx, shot in enumerate(shot_definitions):
            start_sec = shot.get("start_sec", 0.0)
            start_idx = int(start_sec * sr)

            # Insert transition whoosh on cuts (skip initial opening frame)
            if s_idx > 0 and start_idx < total_samples:
                # Center whoosh around the cut point (offset -0.25s)
                w_offset = max(0, start_idx - int(0.25 * sr))
                w_len = min(len(whoosh_stem), total_samples - w_offset)
                if w_len > 0:
                    sfx_bus[w_offset : w_offset + w_len] += whoosh_stem[:w_len] * whoosh_gain

            # Insert dedicated shot Foley SFX cue
            sfx_cue = shot.get("sfx_cue")
            if sfx_cue:
                cue_stem = self.load_sfx(sfx_cue, target_sr=sr)
                cue_gain = 10.0 ** (foley_db / 20.0)
                # Offset by 0.1s into the scene
                c_offset = min(total_samples - 1, start_idx + int(0.1 * sr))
                c_len = min(len(cue_stem), total_samples - c_offset)
                if c_len > 0:
                    sfx_bus[c_offset : c_offset + c_len] += cue_stem[:c_len] * cue_gain

        # 3. 432Hz Ambient Healing Sound Bed
        from common.audio_mastering import generate_ayurveda_ambient_bed
        temp_ambient = out_p.parent / "temp_ambient_bed.wav"
        generate_ayurveda_ambient_bed(total_sec, temp_ambient, sample_rate=sr, target_db=ambient_drone_db)
        ambient_data, _ = sf.read(str(temp_ambient), dtype="float32")
        if temp_ambient.exists():
            temp_ambient.unlink()

        # Align length
        amb_len = min(total_samples, len(ambient_data))
        ambient_track = np.zeros(total_samples, dtype=np.float32)
        ambient_track[:amb_len] = ambient_data[:amb_len]

        # 4. Sum Multi-Track Buses with Soft-Knee Analog Limiter
        # Voice (0dB) + Foley (-9dB) + Whoosh (-11dB) + Ambient (-22dB)
        summed = voice_norm + sfx_bus + ambient_track

        # Soft-knee saturation limiter to prevent digital clipping
        mastered = np.tanh(summed * 0.98)

        sf.write(str(out_p), mastered.astype(np.float32), sr)
        logger.info(f"[+] Theatrical Foley soundtrack mastered successfully: {out_p.name} ({total_sec:.1f}s)")
        return out_p


def test_foley_pipeline() -> bool:
    """Verifies that the Foley sound director generates and mixes audio properly."""
    director = SoundDirector()
    test_shots = [
        {"start_sec": 0.0, "sfx_cue": "ice_clink.wav"},
        {"start_sec": 3.2, "sfx_cue": "cold_water_splash.wav"},
        {"start_sec": 6.5, "sfx_cue": "sub_bass_drop.wav"},
        {"start_sec": 9.8, "sfx_cue": "brass_pour.wav"},
        {"start_sec": 13.0, "sfx_cue": "steam_hiss.wav"},
        {"start_sec": 16.5, "sfx_cue": "ethereal_chime.wav"},
    ]

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir)
        dummy_voice = tmp_p / "dummy_voice.wav"
        out_master = tmp_p / "mastered.wav"

        # Create 20-second dummy voice tone
        sr = 24000
        t = np.linspace(0, 20.0, int(20.0 * sr), endpoint=False, dtype=np.float32)
        v_data = (0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        sf.write(str(dummy_voice), v_data, sr)

        res = director.build_theatrical_soundtrack(dummy_voice, out_master, test_shots)
        if res.exists() and res.stat().st_size > 1000:
            print("[+] SoundDirector test passed! Mastered audio created.")
            return True
    return False


if __name__ == "__main__":
    test_foley_pipeline()
