# BunkerCut Studio — Galactic Highway Style Video Maker

## Overview
Full-stack AI video production studio modeled after `RmyjNoz2pw4` (*"Bunker Survival 1 Year"* by Galactic Highway).

## Architecture
- **Backend (`server/`)**: Python `aiohttp` async server on port `8788`.
  - `server/config.py`: Resolves `OPENROUTER_API_KEY` from environment, `.env`, runtime UI settings, or `~/.cursor/mcp.json`.
  - `server/openrouter.py`:
    - Storyboard & script generation via `/api/v1/chat/completions` (`google/gemini-2.5-flash`, `anthropic/claude-sonnet-4.5`, `openai/gpt-4o-mini`).
    - 2D stick-figure illustration generation via `/api/v1/images` (`bytedance-seed/seedream-5-0-flash`, `google/gemini-nano-banana-2.1`, `black-forest-labs/flux-3-image`, `openai/gpt-image-2.5-sunburst`, `qwen/qwen-image-2.1-turbo`) with `input_references` character consistency conditioning.
    - Multi-engine voice synthesis and zero-shot narrator voice cloning via `/api/v1/audio/speech` (`fish-audio/s2.1-pro` with `reference/narrator_sample.wav`, `elevenlabs/eleven-flash-v2.5`, `elevenlabs/eleven-v4-turbo`, `hexgrad/kokoro-82m`, `google/gemini-3.8-flash-lite-tts` with automatic 24kHz PCM-to-MP3 conversion, and `x-ai/grok-voice-tts-1.0`).
  - `server/sfx.py`: Procedural 24kHz WAV synthesizer (`numpy`) for survival sound effects (`siren`, `radio_static`, `hatch_seal`, `geiger`, `power_down`, `heartbeat`, `explosion_rumble`, `bunker_hum`) and dark ambient bunker drone bed.
  - `server/renderer.py`: FFmpeg 1080p 30fps cinema assembly pipeline using `libopenh264` (`avc1`) + `aac`, smooth `zoompan` camera motions, ASS burned-in subtitles, SRT export, and YouTube chapters.
- **Frontend (`web/`)**: React 19 + TypeScript + Vite 6 + Tailwind v4 on port `5173` (proxies `/api` and `/media` to `127.0.0.1:8788`).

## Commands
- Start backend: `python3 -m server.app` (runs on `http://0.0.0.0:8788`)
- Start frontend dev server: `cd web && bun run dev` (runs on `http://0.0.0.0:5173`)
- Build frontend for production: `cd web && bun run build`
- Generate/verify demo project: `python3 -m server.seed_demo`

## Platform Notes
- On Fedora Linux (`ffmpeg-free`), use `-c:v libopenh264 -b:v 4500k -maxrate 6000k` instead of `libx264` for H.264 MP4 encoding.
- When downloading YouTube reference videos with `yt-dlp`, pass `--ignore-errors --js-runtimes node` so subtitle rate-limiting (`HTTP 429`) does not abort video/metadata extraction.
