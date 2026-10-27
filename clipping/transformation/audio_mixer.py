"""
Audio mixer for transformative short-form video.
Completely eliminates source video audio, overlays clean neural voiceover commentary,
and composites a vectorized ambient cinematic pulse bed.
"""

import logging
import wave
from pathlib import Path
import numpy as np

logger = logging.getLogger("clipping.transformation.audio_mixer")


def generate_ambient_bed(duration_sec: float, output_path: Path, sample_rate: int = 44100) -> Path:
    """
    Vectorized synthesis of a subtle, warm ambient pulse bed using NumPy.
    Runs in <50ms.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)

    # Sub-bass warmth: 60Hz + 90Hz
    f1, f2 = 60.0, 90.0
    lfo = 0.8 + 0.2 * np.sin(2.0 * np.pi * 0.2 * t)
    fade_in = np.clip(t / 1.5, 0.0, 1.0)
    fade_out = np.clip((duration_sec - t) / 2.0, 0.0, 1.0)
    fade = fade_in * fade_out

    waveform = np.sin(2.0 * np.pi * f1 * t) * 0.6 + np.sin(2.0 * np.pi * f2 * t) * 0.4
    amplitude = (950.0 * waveform * lfo * fade).clip(-32767, 32767).astype(np.int16)

    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(amplitude.tobytes())

    return output_path


def compose_clip_audio(commentary_audio_path: Path, output_master_path: Path) -> Path:
    """
    Ensures commentary audio exists and generates a master track.
    If moviepy is available, composites commentary with ambient bed;
    otherwise uses the commentary directly.
    """
    output_master_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from faceless_content.moviepy_compat import (
            AudioFileClip,
            CompositeAudioClip,
            scale_clip_volume,
            is_moviepy_available,
        )

        if is_moviepy_available():
            v_clip = AudioFileClip(str(commentary_audio_path))
            duration = v_clip.duration

            temp_bed = output_master_path.parent / f"temp_bed_{output_master_path.stem}.wav"
            generate_ambient_bed(duration, temp_bed)

            bed_clip = AudioFileClip(str(temp_bed))
            bed_scaled = scale_clip_volume(bed_clip, 0.18)
            v_scaled = scale_clip_volume(v_clip, 1.0)

            master = CompositeAudioClip([v_scaled, bed_scaled])
            master.write_audiofile(
                str(output_master_path),
                fps=44100,
                nbytes=2,
                codec="pcm_s16le" if output_master_path.suffix == ".wav" else None,
                logger=None,
            )

            v_clip.close()
            bed_clip.close()
            master.close()
            if temp_bed.exists():
                temp_bed.unlink()

            logger.info(f"Master composite audio compiled at: {output_master_path}")
            return output_master_path

    except Exception as e:
        logger.warning(f"Audio composition fallback ({e}). Using voiceover directly.")

    return commentary_audio_path
