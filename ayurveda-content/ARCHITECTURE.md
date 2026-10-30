# Ayurveda Content Automation - System Architecture

## Objective
Build a fully automated pipeline to generate professional, 9:16 vertical videos (Shorts/Reels) about Ayurveda in English and Hindi. 

## Architecture Split
We are splitting the logic into two distinct engines to ensure professional rendering (moving away from MoviePy for visuals).

### 1. The Python Orchestrator (`/orchestrator`)
*   **Role:** The backend brain.
*   **Tasks:**
    *   Query LLM (Ollama/Qwen or Gemini API) for a structured JSON script (Hook, Body, Visual Keywords, CTA) in EN/HI.
    *   Generate TTS audio using Kokoro-82M (local via Ollama/GPU) or ElevenLabs API.
    *   Generate word-level timestamped captions (JSON format) using local Whisper.
    *   Download 9:16 stock videos via Pexels API based on LLM visual keywords.
    *   Trigger the Remotion build via CLI, passing the downloaded assets as props.
    *   Upload the final output to social media APIs.

### 2. The React Rendering Engine (`/renderer`)
*   **Role:** Professional video compositing using standard React/CSS.
*   **Tech:** Remotion (npx create-video)
*   **Tasks:**
    *   Accept audio, video clips, and word-level Whisper JSON as CLI props.
    *   Render dynamic, bouncy TikTok-style captions based on the Whisper timestamps.
    *   Stitch and crossfade the Pexels stock footage over the audio.
    *   Export a final `output.mp4`.