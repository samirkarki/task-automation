"""
Karaoke Subtitle Styler for YouTube Shorts.
Generates Advanced SubStation Alpha (.ass) subtitle files with word-level highlighting
in the high-retention viral style (Hormozi / OpusClip / CapCut).
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


ASS_HEADER = """[Script Info]
Title: Viral Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,68,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,40,40,620,1
Style: Highlight,Arial Black,74,&H0000FFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,105,105,0,0,1,6,4,2,40,40,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


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
        # 1. Use Whisper WordSegments
        raw_words = word_segments_or_text
        # Group into 3-4 word cards
        card_size = 3
        for i in range(0, len(raw_words), card_size):
            chunk = raw_words[i : i + card_size]
            card_start = chunk[0].start
            card_end = chunk[-1].end

            # For each word in chunk, produce a highlight slice
            for active_idx, active_word in enumerate(chunk):
                w_start = active_word.start
                w_end = active_word.end

                line_parts = []
                for idx, w in enumerate(chunk):
                    if idx == active_idx:
                        # Highlighted active word in bright yellow
                        line_parts.append(f"{{\\c&H0000FFFF&\\fscx108\\fscy108}}{w.word.upper()}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c&H00FFFFFF&}}{w.word.upper()}{{\\r}}")

                event_line = (
                    f"Dialogue: 0,{format_ass_time(w_start)},{format_ass_time(w_end)},"
                    f"Default,,0,0,0,,{' '.join(line_parts)}"
                )
                events.append(event_line)

    else:
        # 2. Text fallback: split into proportionate cards
        text = str(word_segments_or_text).strip()
        words = text.split()
        card_size = 4
        chunks = [" ".join(words[i : i + card_size]) for i in range(0, len(words), card_size)]
        if not chunks:
            chunks = ["CRITICAL BUSINESS STRATEGY", "SYSTEMS OVER HUSTLE", "MAXIMIZE CAPITAL LEVERAGE"]

        card_dur = max(1.2, total_duration / float(len(chunks)))
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
                    if sub_i == widx:
                        line_parts.append(f"{{\\c&H0000FFFF&\\fscx108\\fscy108}}{sw.upper()}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c&H00FFFFFF&}}{sw.upper()}{{\\r}}")

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
