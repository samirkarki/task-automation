"""
Karaoke Subtitle Styler for YouTube Shorts.
Generates Advanced SubStation Alpha (.ass) subtitle files with word-level highlighting
in high-retention viral styles adapted per profile (GTA6 gaming bounce, MrBeast impact, etc.).
Guarantees text perfectly fits the 9:16 mobile window without horizontal overflow.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from clipping.models import WordSegment
from clipping.profiles.base import ClipProfile

logger = logging.getLogger("clipping.transformation.subtitle_styler")


def format_ass_time(seconds: float) -> str:
    """Formats float seconds into ASS timestamp format: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_header(profile: Optional[ClipProfile] = None) -> str:
    """
    Constructs dynamic ASS header with typography, colors, and margins matching the active profile.
    """
    style = profile.subtitle_style if profile else {}

    font_name = style.get("font_family", "Montserrat ExtraBold, Arial Black, Impact").split(",")[0].strip()
    font_size = style.get("font_size", 52)
    prim_color = style.get("primary_color", "&H0000FFFF")  # Highlight color (yellow default)
    sec_color = style.get("secondary_color", "&H00FFFFFF")   # Base text (white default)
    outline_color = style.get("outline_color", "&H00000000")
    outline_w = style.get("outline_width", 4.5)
    shadow_d = style.get("shadow_depth", 2.5)

    # In split-screen mode, vertical margin sits right at the divider boundary (y ≈ 680)
    default_margin_v = 640 if (profile and profile.layout_mode == "smart_split_screen") else 680
    margin_v = style.get("vertical_margin", default_margin_v)

    header = f"""[Script Info]
Title: Viral Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{sec_color},{prim_color},{outline_color},&H90000000,-1,0,0,0,100,100,0,0,1,{outline_w},{shadow_d},2,80,120,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def _chunk_word_segments(words: List[WordSegment], max_chars: int = 15, max_words: int = 2) -> List[List[WordSegment]]:
    """
    Chunks word segments into compact 1-2 word cards (max 15 characters).
    Ensures every phrase fits comfortably inside the 1080px vertical screen.
    """
    chunks = []
    current_chunk = []
    current_chars = 0

    for w in words:
        clean_word = w.word.strip()
        if not clean_word:
            continue
        w_len = len(clean_word)

        if not current_chunk:
            current_chunk.append(w)
            current_chars = w_len
        elif len(current_chunk) >= max_words or (current_chars + 1 + w_len) > max_chars:
            chunks.append(current_chunk)
            current_chunk = [w]
            current_chars = w_len
        else:
            current_chunk.append(w)
            current_chars += 1 + w_len

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _chunk_plain_text(text: str, max_chars: int = 15, max_words: int = 2) -> List[str]:
    """Splits plain text into compact 1-2 word cards (max 15 characters)."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_chars = 0

    for w in words:
        clean_word = w.strip()
        if not clean_word:
            continue
        w_len = len(clean_word)

        if not current_chunk:
            current_chunk.append(clean_word)
            current_chars = w_len
        elif len(current_chunk) >= max_words or (current_chars + 1 + w_len) > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = [clean_word]
            current_chars = w_len
        else:
            current_chunk.append(clean_word)
            current_chars += 1 + w_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks


def generate_karaoke_subtitles(
    word_segments_or_text: Union[List[WordSegment], str],
    output_path: Path,
    total_duration: float = 40.0,
    profile: Optional[ClipProfile] = None,
) -> Path:
    """
    Generates .ass subtitle file with word-by-word karaoke highlighting,
    configured according to the active ClipProfile.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events: List[str] = []

    style = profile.subtitle_style if profile else {}
    highlight_color = style.get("primary_color", "&H0000FFFF")  # Default yellow
    base_color = style.get("secondary_color", "&H00FFFFFF")     # Default white

    # Animation tag: scale bounce 112% for active word
    pulse_tag = "{\\fscx112\\fscy112}"

    if isinstance(word_segments_or_text, list) and len(word_segments_or_text) > 0 and isinstance(word_segments_or_text[0], WordSegment):
        chunks = _chunk_word_segments(word_segments_or_text, max_chars=14, max_words=2)

        for chunk in chunks:
            for active_idx, active_word in enumerate(chunk):
                w_start = active_word.start
                w_end = active_word.end
                if w_end <= w_start:
                    w_end = w_start + 0.15

                line_parts = []
                for idx, w in enumerate(chunk):
                    clean_w = w.word.strip().upper()
                    if idx == active_idx:
                        line_parts.append(f"{{\\c{highlight_color}&{pulse_tag}}}{clean_w}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c{base_color}&}}{clean_w}{{\\r}}")

                event_line = (
                    f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},"
                    f"Default,,0,0,0,,{' '.join(line_parts)}"
                )
                events.append(event_line)

    else:
        text = str(word_segments_or_text).strip()
        chunks = _chunk_plain_text(text, max_chars=14, max_words=2)
        if not chunks:
            chunks = ["GTA 6", "VIRAL MOMENT", "STREAM HIGHLIGHT"]

        card_dur = max(0.8, total_duration / float(len(chunks)))
        for idx, chunk in enumerate(chunks):
            start_t = idx * card_dur
            end_t = min(total_duration, (idx + 1) * card_dur)
            card_words = chunk.split()

            sub_step = (end_t - start_t) / float(len(card_words))
            for widx, w in enumerate(card_words):
                w_start = start_t + widx * sub_step
                w_end = min(end_t, w_start + sub_step)

                line_parts = []
                for sub_i, sw in enumerate(card_words):
                    clean_sw = sw.strip().upper()
                    if sub_i == widx:
                        line_parts.append(f"{{\\c{highlight_color}&{pulse_tag}}}{clean_sw}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c{base_color}&}}{clean_sw}{{\\r}}")

                event_line = (
                    f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},"
                    f"Default,,0,0,0,,{' '.join(line_parts)}"
                )
                events.append(event_line)

    full_ass = build_ass_header(profile) + "\n".join(events) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_ass)

    logger.info(f"Karaoke .ass subtitles generated at: {output_path} ({len(events)} events)")
    return output_path
