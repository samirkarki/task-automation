"""
Karaoke Subtitle Styler for YouTube Shorts.
Generates Advanced SubStation Alpha (.ass) subtitle files with word-level highlighting
in the high-retention viral style (Hormozi / OpusClip / CapCut).
Guarantees text perfectly fits the 9:16 mobile window without horizontal overflow.
"""

import logging
from pathlib import Path
from typing import List, Union
from clipping.models import WordSegment

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


# Screen dimensions: 1080 x 1920 (9:16 vertical)
# MarginL: 80px left padding
# MarginR: 130px right padding (protects against YouTube like/comment buttons overlay)
# MarginV: 680px from bottom (places captions in lower-middle safe zone)
# Fontsize: 50 (clean, readable, prevents text overflowing 1080px width)
ASS_HEADER = """[Script Info]
Title: Viral Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,50,&H00FFFFFF,&H0000FFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4.5,2.5,2,80,130,680,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


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
    """
    Splits plain text into compact 1-2 word cards (max 15 characters).
    """
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
) -> Path:
    """
    Generates .ass subtitle file with word-by-word karaoke highlighting.
    Accepts either granular WordSegments or plain commentary text.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events: List[str] = []

    if isinstance(word_segments_or_text, list) and len(word_segments_or_text) > 0 and isinstance(word_segments_or_text[0], WordSegment):
        # 1. Use Whisper WordSegments with dynamic compact chunking (1-2 words per card)
        chunks = _chunk_word_segments(word_segments_or_text, max_chars=15, max_words=2)

        for chunk in chunks:
            # For each word in chunk, produce a highlight slice
            for active_idx, active_word in enumerate(chunk):
                w_start = active_word.start
                w_end = active_word.end
                if w_end <= w_start:
                    w_end = w_start + 0.15

                line_parts = []
                for idx, w in enumerate(chunk):
                    clean_w = w.word.strip().upper()
                    if idx == active_idx:
                        # Highlighted active word: bright yellow + gentle 6% pulse
                        line_parts.append(f"{{\\c&H0000FFFF&\\fscx106\\fscy106}}{clean_w}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c&H00FFFFFF&}}{clean_w}{{\\r}}")

                event_line = (
                    f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},"
                    f"Default,,0,0,0,,{' '.join(line_parts)}"
                )
                events.append(event_line)

    else:
        # 2. Text fallback: split into compact 1-2 word cards
        text = str(word_segments_or_text).strip()
        chunks = _chunk_plain_text(text, max_chars=15, max_words=2)
        if not chunks:
            chunks = ["CRITICAL", "BUSINESS", "STRATEGY", "SYSTEMS OVER", "HUSTLE", "MAXIMIZE", "LEVERAGE"]

        card_dur = max(0.8, total_duration / float(len(chunks)))
        for idx, chunk in enumerate(chunks):
            start_t = idx * card_dur
            end_t = min(total_duration, (idx + 1) * card_dur)
            card_words = chunk.split()

            # Word-level sub-timing
            sub_step = (end_t - start_t) / float(len(card_words))
            for widx, w in enumerate(card_words):
                w_start = start_t + widx * sub_step
                w_end = min(end_t, w_start + sub_step)

                line_parts = []
                for sub_i, sw in enumerate(card_words):
                    clean_sw = sw.strip().upper()
                    if sub_i == widx:
                        line_parts.append(f"{{\\c&H0000FFFF&\\fscx106\\fscy106}}{clean_sw}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c&H00FFFFFF&}}{clean_sw}{{\\r}}")

                event_line = (
                    f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},"
                    f"Default,,0,0,0,,{' '.join(line_parts)}"
                )
                events.append(event_line)

    full_ass = ASS_HEADER + "\n".join(events) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_ass)

    logger.info(f"Karaoke .ass subtitles generated at: {output_path} ({len(events)} events)")
    return output_path
