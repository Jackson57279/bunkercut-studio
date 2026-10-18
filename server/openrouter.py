import asyncio
import base64
import io
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional
import httpx
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .config import CAST_DIR, REFERENCE_DIR, get_openrouter_api_key

DEFAULT_CAST = [
    {
        "id": "alex",
        "name": "Alex (The Survivor)",
        "role": "Lead Protagonist",
        "badge": "Orange Cap",
        "accent": "#FF5500",
        "default_voice": "clone_reference",
        "visual_description": (
            "A 2D stick-figure character with thin uniform black stick limbs (#000000), a simple round white head, "
            "expressive minimalist cartoon eyes and mouth, messy brown hair sticking out beneath a bright orange baseball cap, and simple white oval feet."
        ),
        "reference_url": "/media/reference/clean_character_anchor.png",
        "reference_file": str(REFERENCE_DIR / "clean_character_anchor.png"),
    },
    {
        "id": "elena",
        "name": "Dr. Elena (The Engineer)",
        "role": "Systems & Technical Specialist",
        "badge": "Yellow Hard-Hat",
        "accent": "#EAB308",
        "default_voice": "sarah",
        "visual_description": (
            "A 2D stick-figure engineer with thin uniform black stick limbs (#000000), a simple round white head, "
            "minimalist round black-framed eyeglasses, dark hair tied back under a bright yellow industrial hard-hat, and simple white oval feet."
        ),
        "reference_url": "/media/reference/cast/char_elena.png",
        "reference_file": str(CAST_DIR / "char_elena.png"),
    },
    {
        "id": "marcus",
        "name": "Commander Marcus",
        "role": "Operations & Tactical Lead",
        "badge": "Olive Beret",
        "accent": "#22C55E",
        "default_voice": "brian",
        "visual_description": (
            "A 2D stick-figure commander with thin uniform black stick limbs (#000000), a simple round white head, "
            "sharp serious eyebrows, short dark hair beneath an olive-green military beret, a small black radio headset mic, and simple white oval feet."
        ),
        "reference_url": "/media/reference/cast/char_marcus.png",
        "reference_file": str(CAST_DIR / "char_marcus.png"),
    },
    {
        "id": "maya",
        "name": "Dr. Maya (Field Medic)",
        "role": "Biologist & Medical Officer",
        "badge": "Blue Medical Cap",
        "accent": "#3B82F6",
        "default_voice": "alice",
        "visual_description": (
            "A 2D stick-figure medic with thin uniform black stick limbs (#000000), a simple round white head, "
            "expressive calm cartoon eyes, shoulder-length brown hair under a cobalt-blue scrub cap featuring a tiny white cross emblem, and simple white oval feet."
        ),
        "reference_url": "/media/reference/cast/char_maya.png",
        "reference_file": str(CAST_DIR / "char_maya.png"),
    },
    {
        "id": "jonah",
        "name": "Jonah (The Scout)",
        "role": "Field Recon & Logistics",
        "badge": "Red Beanie",
        "accent": "#EF4444",
        "default_voice": "callum",
        "visual_description": (
            "A 2D stick-figure scout with thin uniform black stick limbs (#000000), a simple round white head, "
            "alert cartoon eyes, scruffy dark hair under a crimson-red knit beanie, wearing a compact olive-green field backpack, and simple white oval feet."
        ),
        "reference_url": "/media/reference/cast/char_jonah.png",
        "reference_file": str(CAST_DIR / "char_jonah.png"),
    },
]

STYLE_PRESETS = {
    "galactic_highway": {
        "id": "galactic_highway",
        "name": "Galactic Highway 2D Stick-Figure (Reference Style)",
        "description": "Stark pure white (#FFFFFF) background or clean 2D line-art rooms, thin black stick-figure limbs, round white head, flat 2D vector props & bold uppercase diagram labels.",
        "prompt_prefix": (
            "Minimalist 2D stick-figure explainer illustration on a stark pure white (#FFFFFF) background. "
            "Clean flat vector line art with crisp uniform black outlines (#000000), flat muted color fills on props and objects, "
            "zero gradients, zero 3D shading, Galactic Highway YouTube animation drawing style. "
        ),
        "character_desc": DEFAULT_CAST[0]["visual_description"],
    },
    "vault_manual": {
        "id": "vault_manual",
        "name": "Technical Manual Stick-Figure",
        "description": "Clean 2D stick-figure line art on crisp white background with technical cutaway diagrams and stencil labels.",
        "prompt_prefix": (
            "Clean 2D technical manual stick-figure explainer illustration on a pure white (#FFFFFF) background. "
            "Bold black ink outlines, flat muted olive, steel grey, and hazard orange color fills, clear diagram aesthetics. "
        ),
        "character_desc": DEFAULT_CAST[0]["visual_description"],
    },
    "flat_infographic": {
        "id": "flat_infographic",
        "name": "Clean Vector Cutaway & Diagram Style",
        "description": "Crisp 2D stick-figure and geometric flat vector illustrations with high-legibility cutaway views and labels.",
        "prompt_prefix": (
            "Clean 2D flat vector stick-figure explainer illustration on a pure white (#FFFFFF) background, crisp black outlines, "
            "clear educational diagram aesthetic, flat colors, high legibility. "
        ),
        "character_desc": DEFAULT_CAST[0]["visual_description"],
    },
    "graphic_noir": {
        "id": "graphic_noir",
        "name": "High-Contrast Ink Stick-Figure",
        "description": "Stark ink line-art stick-figure style with high-contrast focal highlights.",
        "prompt_prefix": (
            "Stark 2D ink line-art stick-figure illustration on a clean white (#FFFFFF) background, crisp black outlines, "
            "dramatic contrast with safety-orange and red focal accents. "
        ),
        "character_desc": DEFAULT_CAST[0]["visual_description"],
    },
}

DURATION_PRESETS = [
    {
        "id": "explainer_3m",
        "name": "~3 Min Explainer",
        "minutes": 3,
        "scene_count": 24,
        "chapters": 3,
        "desc": "24 beats across 3 chapters (~3 mins)",
    },
    {
        "id": "episode_8m",
        "name": "~8 Min Feature",
        "minutes": 8,
        "scene_count": 64,
        "chapters": 6,
        "desc": "64 beats across 6 chapters (~8 mins)",
    },
    {
        "id": "deepdive_12m",
        "name": "~12 Min Documentary",
        "minutes": 12,
        "scene_count": 96,
        "chapters": 8,
        "desc": "96 beats across 8 chapters (~12 mins)",
    },
    {
        "id": "mega_20m",
        "name": "~20 Min Mega Episode",
        "minutes": 20,
        "scene_count": 160,
        "chapters": 12,
        "desc": "160 beats across 12 chapters (~20 mins)",
    },
]

VISUAL_DENSITY_MODES = [
    {
        "id": "smart_2x",
        "name": "Smart 2-Beat Multi-Angle (50% Lower Cost · Recommended)",
        "divisor": 2,
        "description": "Generates 1 wide high-detail illustration per 2 narrative beats and cuts between Wide Establishing and 1.26x Detail Focus crops.",
    },
    {
        "id": "smart_3x",
        "name": "Ultra-Economy 3-Angle (67% Lower Cost · Best for 20-Min Videos)",
        "divisor": 3,
        "description": "Generates 1 master illustration per 3 beats and cuts across Wide, Left Subject Focus, and Right Prop/Diagram Focus.",
    },
    {
        "id": "every_beat",
        "name": "Every Beat Unique (100% Custom Frame per Beat)",
        "divisor": 1,
        "description": "Generates a separate OpenRouter image for every individual narrative beat.",
    },
]

IMAGE_MODELS = [
    {
        "id": "bytedance-seed/seedream-5-0-flash",
        "name": "ByteDance Seedream 5.0 Flash",
        "badge": "Best Value · Exact Stick-Figure Style",
        "price_est": "$0.018 / image",
        "cost_num": 0.018,
        "supports_reference": True,
    },
    {
        "id": "google/gemini-nano-banana-2.1",
        "name": "Google Nano Banana 2.1 (Gemini Image)",
        "badge": "Best Typography & Diagram Labels",
        "price_est": "$0.036 / image",
        "cost_num": 0.036,
        "supports_reference": True,
    },
    {
        "id": "qwen/qwen-image-2.1-turbo",
        "name": "Qwen Image 2.1 Turbo",
        "badge": "Fast Batch Generation",
        "price_est": "$0.020 / image",
        "cost_num": 0.020,
        "supports_reference": True,
    },
    {
        "id": "black-forest-labs/flux-3-image-klein",
        "name": "FLUX 3 Image Klein",
        "badge": "Clean Line Art",
        "price_est": "$0.025 / image",
        "cost_num": 0.025,
        "supports_reference": True,
    },
    {
        "id": "openai/gpt-image-2.5-sunburst",
        "name": "OpenAI GPT Image 2.5 Sunburst",
        "badge": "Precision Diagrams & Text",
        "price_est": "$0.040 / image",
        "cost_num": 0.040,
        "supports_reference": True,
    },
]

FEATURED_HUMAN_VOICES = [
    # --- ULTRA-NATURAL FEMALE VOICES ---
    {
        "id": "female_harper",
        "gender": "female",
        "name": "Harper — Warm Conversational American",
        "subtitle": "Microsoft MAI-Voice 2.1 (#1 Audio Realism)",
        "tts_model": "microsoft/mai-voice-2.1",
        "voice": "en-US-Harper:MAI-Voice-2.1",
        "badge": "Top Female · Ultra-Human",
    },
    {
        "id": "female_aoede",
        "gender": "female",
        "name": "Aoede — Intimate Studio Storyteller",
        "subtitle": "Google Gemini 3.8 Flash TTS (#1 Overall ELO)",
        "tts_model": "google/gemini-3.8-flash-tts",
        "voice": "Aoede",
        "badge": "Best Value · $0.02 / 20m",
    },
    {
        "id": "female_jessica",
        "gender": "female",
        "name": "Jessica — Natural Unscripted Creator",
        "subtitle": "ElevenLabs v3 Conversational",
        "tts_model": "elevenlabs/eleven-v3-conversational",
        "voice": "jessica",
        "badge": "Zero AI Cadence",
    },
    {
        "id": "female_olivia",
        "gender": "female",
        "name": "Olivia — Calm Documentary Narrator",
        "subtitle": "Microsoft MAI-Voice 2.1",
        "tts_model": "microsoft/mai-voice-2.1",
        "voice": "en-US-Olivia:MAI-Voice-2.1",
        "badge": "Warm & Grounded",
    },
    {
        "id": "female_matilda",
        "gender": "female",
        "name": "Matilda — Engaging Storyteller",
        "subtitle": "ElevenLabs v4",
        "tts_model": "elevenlabs/eleven-v4",
        "voice": "matilda",
        "badge": "Studio Expressive",
    },
    {
        "id": "female_sesame",
        "gender": "female",
        "name": "Maya — Real Podcast Mic & Breath",
        "subtitle": "Sesame CSM-1B Conversational",
        "tts_model": "sesame/csm-1b",
        "voice": "conversational_a",
        "badge": "Podcast Realism",
    },
    # --- ULTRA-NATURAL MALE VOICES ---
    {
        "id": "male_grant",
        "gender": "male",
        "name": "Grant — Grounded Documentary Host",
        "subtitle": "Microsoft MAI-Voice 2.1 (#1 Audio Realism)",
        "tts_model": "microsoft/mai-voice-2.1",
        "voice": "en-US-Grant:MAI-Voice-2.1",
        "badge": "Top Male · Ultra-Human",
    },
    {
        "id": "male_charon",
        "gender": "male",
        "name": "Charon — Deep Late-Night Storyteller",
        "subtitle": "Google Gemini 3.8 Flash TTS (#1 Overall ELO)",
        "tts_model": "google/gemini-3.8-flash-tts",
        "voice": "Charon",
        "badge": "Best Value · $0.02 / 20m",
    },
    {
        "id": "male_chris",
        "gender": "male",
        "name": "Chris — Relaxed Conversational Host",
        "subtitle": "ElevenLabs v3 Conversational",
        "tts_model": "elevenlabs/eleven-v3-conversational",
        "voice": "chris",
        "badge": "Zero AI Cadence",
    },
    {
        "id": "male_jasper",
        "gender": "male",
        "name": "Jasper — Warm Investigative Narrator",
        "subtitle": "Microsoft MAI-Voice 2.1",
        "tts_model": "microsoft/mai-voice-2.1",
        "voice": "en-US-Jasper:MAI-Voice-2.1",
        "badge": "Warm & Natural",
    },
    {
        "id": "male_brian",
        "gender": "male",
        "name": "Brian — Rich Cinema Documentary",
        "subtitle": "ElevenLabs v4",
        "tts_model": "elevenlabs/eleven-v4",
        "voice": "brian",
        "badge": "Deep Studio Mic",
    },
    {
        "id": "male_cloned",
        "gender": "male",
        "name": "Galactic Highway Cloned Narrator",
        "subtitle": "Fish Audio S2.1 Pro (Cloned from RmyjNoz2pw4)",
        "tts_model": "fish-audio/s2.1-pro",
        "voice": "clone_reference",
        "badge": "Reference Clone",
    },
]

TTS_MODELS = [
    {
        "id": "microsoft/mai-voice-2.1",
        "name": "Microsoft MAI-Voice 2.1 (#1 Audio Realism Benchmark)",
        "badge": "Most Human · Male & Female",
        "mode": "standard",
        "cost_per_20m": "$0.15",
        "voices": [
            {"id": "en-US-Harper:MAI-Voice-2.1", "name": "Harper (Female · Warm Conversational American)", "gender": "female"},
            {"id": "en-US-Olivia:MAI-Voice-2.1", "name": "Olivia (Female · Intimate Documentary Storyteller)", "gender": "female"},
            {"id": "en-US-Sage:MAI-Voice-2.1", "name": "Sage (Female · Calm Investigative Host)", "gender": "female"},
            {"id": "en-GB-Emily:MAI-Voice-2.1", "name": "Emily (Female · Natural British Storyteller)", "gender": "female"},
            {"id": "en-AU-Isla:MAI-Voice-2.1", "name": "Isla (Female · Warm Australian Narrator)", "gender": "female"},
            {"id": "en-US-Grant:MAI-Voice-2.1", "name": "Grant (Male · Grounded American Storyteller)", "gender": "male"},
            {"id": "en-US-Jasper:MAI-Voice-2.1", "name": "Jasper (Male · Warm Documentary Narrator)", "gender": "male"},
            {"id": "en-US-Ethan:MAI-Voice-2.1", "name": "Ethan (Male · Relaxed Podcast Host)", "gender": "male"},
            {"id": "en-GB-Harry:MAI-Voice-2.1", "name": "Harry (Male · Natural British Narrator)", "gender": "male"},
        ],
    },
    {
        "id": "google/gemini-3.8-flash-tts",
        "name": "Google Gemini 3.8 Flash TTS (#1 Overall ELO · Directed Prosody)",
        "badge": "Best Value Human · $0.02 / 20m",
        "mode": "pcm",
        "cost_per_20m": "$0.02",
        "voices": [
            {"id": "Aoede", "name": "Aoede (Female · Warm, Natural Studio Storyteller)", "gender": "female"},
            {"id": "Kore", "name": "Kore (Female · Calm, Intimate Documentary Voice)", "gender": "female"},
            {"id": "Callirrhoe", "name": "Callirrhoe (Female · Expressive Conversational)", "gender": "female"},
            {"id": "Leda", "name": "Leda (Female · Grounded Investigative Narrator)", "gender": "female"},
            {"id": "Charon", "name": "Charon (Male · Deep, Warm Late-Night Storyteller)", "gender": "male"},
            {"id": "Orus", "name": "Orus (Male · Natural, Grounded Documentary Host)", "gender": "male"},
            {"id": "Fenrir", "name": "Fenrir (Male · Gritty, Serious Survival Narrator)", "gender": "male"},
            {"id": "Iapetus", "name": "Iapetus (Male · Relaxed Conversational Creator)", "gender": "male"},
        ],
    },
    {
        "id": "elevenlabs/eleven-v3-conversational",
        "name": "ElevenLabs v3 Conversational (Unscripted Human Cadence)",
        "badge": "Zero AI Announcer Tone",
        "mode": "standard",
        "cost_per_20m": "$0.25",
        "voices": [
            {"id": "jessica", "name": "Jessica (Female · Natural Conversational American)", "gender": "female"},
            {"id": "matilda", "name": "Matilda (Female · Warm Engaging Storyteller)", "gender": "female"},
            {"id": "river", "name": "River (Female · Calm Intimate Late-Night)", "gender": "female"},
            {"id": "lily", "name": "Lily (Female · Warm British Conversational)", "gender": "female"},
            {"id": "alice", "name": "Alice (Female · Clear Documentary Host)", "gender": "female"},
            {"id": "chris", "name": "Chris (Male · Natural Unscripted Conversational)", "gender": "male"},
            {"id": "brian", "name": "Brian (Male · Deep Warm Studio Mic)", "gender": "male"},
            {"id": "eric", "name": "Eric (Male · Relaxed Authentic Storyteller)", "gender": "male"},
            {"id": "george", "name": "George (Male · Warm British Narrator)", "gender": "male"},
            {"id": "callum", "name": "Callum (Male · Gritty Survival Storyteller)", "gender": "male"},
        ],
    },
    {
        "id": "elevenlabs/eleven-v4",
        "name": "ElevenLabs Eleven v4 (Flagship Expressive Studio)",
        "badge": "Flagship Expressive",
        "mode": "standard",
        "cost_per_20m": "$0.40",
        "voices": [
            {"id": "jessica", "name": "Jessica (Female · Warm Conversational)", "gender": "female"},
            {"id": "matilda", "name": "Matilda (Female · Expressive Storyteller)", "gender": "female"},
            {"id": "sarah", "name": "Sarah (Female · Documentary Host)", "gender": "female"},
            {"id": "brian", "name": "Brian (Male · Deep Documentary Narrator)", "gender": "male"},
            {"id": "chris", "name": "Chris (Male · Natural Conversational)", "gender": "male"},
            {"id": "eric", "name": "Eric (Male · Grounded Storyteller)", "gender": "male"},
        ],
    },
    {
        "id": "sesame/csm-1b",
        "name": "Sesame CSM-1B (Conversational Podcast Speech Model)",
        "badge": "Real Breath & Micro-Pauses",
        "mode": "standard",
        "cost_per_20m": "$0.06",
        "voices": [
            {"id": "conversational_a", "name": "Maya (Female · Unscripted Podcast & Breath Realism)", "gender": "female"},
            {"id": "conversational_b", "name": "Miles (Male · Unscripted Podcast & Breath Realism)", "gender": "male"},
        ],
    },
    {
        "id": "canopylabs/orpheus-3b-0.1-ft",
        "name": "Canopy Labs Orpheus 3B (Human Prosody Fine-Tune)",
        "badge": "Natural Prosody",
        "mode": "standard",
        "cost_per_20m": "$0.06",
        "voices": [
            {"id": "tara", "name": "Tara (Female · Expressive Human Prosody)", "gender": "female"},
            {"id": "leah", "name": "Leah (Female · Warm Conversational)", "gender": "female"},
            {"id": "mia", "name": "Mia (Female · Intimate Storyteller)", "gender": "female"},
            {"id": "leo", "name": "Leo (Male · Natural Conversational)", "gender": "male"},
            {"id": "dan", "name": "Dan (Male · Grounded Narrator)", "gender": "male"},
        ],
    },
    {
        "id": "fish-audio/s2.1-pro",
        "name": "Fish Audio S2.1 Pro (Zero-Shot Human Voice Clone)",
        "badge": "Clones RmyjNoz2pw4 Narrator",
        "mode": "clone",
        "cost_per_20m": "$0.04",
        "voices": [
            {"id": "clone_reference", "name": "Galactic Highway Narrator (Cloned from RmyjNoz2pw4)", "gender": "male"},
        ],
    },
]

LLM_MODELS = [
    {"id": "anthropic/claude-sonnet-5.5", "name": "Claude Sonnet 5.5 (Default · Best Deadpan Anti-Slop Writer)"},
    {"id": "anthropic/claude-opus-5.5", "name": "Claude Opus 5.5 (Flagship #1 Reasoning & Writing)"},
    {"id": "google/gemini-4-argon", "name": "Gemini 4 Argon (Fast Long-Horizon Documentary Architect)"},
    {"id": "openai/gpt-6.1-sol", "name": "OpenAI GPT-6.1 Sol (High-Precision Systems & Mechanics)"},
    {"id": "x-ai/grok-4.7", "name": "xAI Grok 4.7 (Direct, Punchy & Unfiltered Cadence)"},
    {"id": "openai/gpt-6-luna", "name": "OpenAI GPT-6 Luna (Ultra-Fast / Low-Cost)"},
]


def _encode_image_data_uri(image_path: Path) -> Optional[str]:
    if not image_path.exists():
        return None
    ext = image_path.suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_json_block(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_obj = cleaned.find("{")
        end_obj = cleaned.rfind("}")
        if start_obj != -1 and end_obj > start_obj:
            return json.loads(cleaned[start_obj : end_obj + 1])
        raise


async def _call_openrouter_llm(
    client: httpx.AsyncClient,
    key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.65,
) -> Any:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    # For reasoning-mandatory models (claude-*-5.5, gpt-6*, gemini-4*), use low/medium reasoning effort for fast structured output
    if any(k in model for k in ("claude-sonnet-5.5", "claude-opus-5.5", "gpt-6", "gemini-4", "step-5", "glm-5")):
        payload["reasoning"] = {"effort": "low"}
    else:
        payload["temperature"] = temperature

    resp = await client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
    )
    if resp.status_code != 200:
        # Fallback to claude-sonnet-5.5 or gpt-6-luna if a specific model rejected params
        fallback_payload = {
            "model": "anthropic/claude-sonnet-5.5" if model != "anthropic/claude-sonnet-5.5" else "openai/gpt-6-luna",
            "messages": payload["messages"],
        }
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=fallback_payload,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter LLM error ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return _extract_json_block(content)


GALACTIC_HIGHWAY_WRITING_BIBLE = """
GOLD-STANDARD WRITING BIBLE (EXACT VOICE OF "BUNKER SURVIVAL 1 YEAR" — RmyjNoz2pw4):

Study these verbatim excerpts from the actual reference transcript. Every single line you write MUST sound like it came from this exact writer:

EXCERPT 1 (Opening & Immediate Stakes):
"The sirens start at 6:14 a.m. Not the monthly test. You know the difference. These don't stop. Your phone buzzes, then again, then it doesn't buzz at all. You have maybe 8 minutes. You grab your go bag, run across the yard, and haul the hatch open."

EXCERPT 2 (Concrete Math & Logistics — NO fluff):
"The average adult needs around 2,000 to 2,500 calories a day. Over 5 years, that's more than 4 million calories. So you stocked about 1,500 lbs of grains, 300 lbs of beans, and hundreds of freeze-dried meals and canned goods, and a few cases of MREs. Not for everyday eating. For the days when something goes wrong."

EXCERPT 3 (Why Hardware Is Built a Specific Way):
"A battery bank on the wall, solar panels on the surface, a generator fed by a row of propane tanks buried in their own vault outside. Propane doesn't go bad like gasoline, and keeping it outside means a leak can't poison your air."

EXCERPT 4 (Silent Cascading Failure):
"Day 71. You're asleep and then you're not. Something woke you up. It takes you a second to realize what. The hum is gone. No lights, no air system, nothing. In a sealed room, the air doesn't go bad all at once. It happens slowly. Every breath you take puts carbon dioxide back into the room, and without the system pulling it out, it builds. First comes the headache, then the confusion. Then you just go to sleep and you don't wake up."

EXCERPT 5 (Mundane Reality, Maintenance & Small Fatal Mistakes):
"Every few months, you swap the air filters on schedule. Not when they look dirty. By the time a filter looks bad, it's already failing. The toilet separates liquids from solids. Liquids drain into a tank buried outside. Solids get a scoop of sawdust after every use. Not glamorous, but in a sealed room, sanitation is survival. Brush and floss every day, no exceptions. Down here, a tooth infection isn't just painful. With no dentist, it can kill you."

EXCERPT 6 (Step-by-Step Physical Repair):
"Day 264. You wake up to your feet in water. A line on the main tank has cracked. You lost almost 100 gallons before you found it. You shut the valve, dry the pipe, clamp it, wrap it in repair tape, and seal it with epoxy. Then you replace the whole section with a spare fitting under an hour."

STRICT ANTI-SLOP RULES (VIOLATING ANY OF THESE FAILS THE SCRIPT):
1. ZERO "FICTION STORY" OR NOVELISTIC PROSE:
   - Do NOT write a fictional story about named characters ("Alex", "Dr. Elena", "Marcus") talking to each other.
   - Always write in plain, deadpan second-person ("You...") or direct practical explanation.
   - NEVER write cheesy transitions like "One moment you're..., the next you're thrust into..." or "With water secured, your mind turns to...".
2. 6TH-GRADE VOCABULARY + REAL ENGINEERING/SURVIVAL MECHANICS:
   - Use simple words (pipes, valves, bleach, sawdust, calories, gallons, filters, bleach, wrench, condensation) to explain smart, hyper-specific real-world mechanics.
   - BANNED AI SLOP WORDS: never use "teeming", "thrust", "disoriented", "crucial", "vital", "paramount", "delve", "testament", "symphony", "tapestry", "cascade", "relentless", "harrowing", "visceral", "unyielding", "bustling", "sustainable", "amidst", "embark", "newfound", "intricacies", "daunting", "meticulously", "peril", "abyss", "sanctuary", "ominous", "moreover", "furthermore".
3. SHORT SENTENCES & FRAGMENTS:
   - Average sentence length: 6 to 14 words.
   - Use deadpan fragments for rhythm ("Not for everyday eating. For the days when something goes wrong." / "No stove, no power, no time, just calories.").
4. VISUAL PROMPT RULES (CLEAN 1-TO-3 OBJECT GALACTIC HIGHWAY FRAMES):
   - Every `visual_prompt` must describe ONE simple, uncluttered 2D illustration on a stark pure white (#FFFFFF) background with at most 1 to 3 clear objects.
   - Never describe a crowded scene with 10 tiny details.
   - If `character_id` is `"diagram"`, describe ONLY 1 to 3 isolated flat 2D vector objects/cutaways on pure white (#FFFFFF) with a bold uppercase label (e.g., "A blue 2,000-gallon water tank next to two white filter cylinders and a bucket labeled TABLETS on a pure white background").
   - If `character_id` is a person (default `"alex"`), describe the 2D stick-figure doing ONE clear physical action with 1 or 2 props (e.g., "The 2D stick-figure in the orange cap standing in ankle-deep water wrapping black tape around a cracked grey pipe next to a red shutoff valve").
"""


async def generate_storyboard_script(
    topic: str,
    scene_count: int = 42,
    style_id: str = "galactic_highway",
    llm_model: str = "anthropic/claude-sonnet-5.5",
    cast_members: Optional[list[dict[str, Any]]] = None,
    custom_notes: str = "",
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> dict[str, Any]:
    key = get_openrouter_api_key()
    if not key:
        raise RuntimeError("OpenRouter API key is not configured.")

    style = STYLE_PRESETS.get(style_id, STYLE_PRESETS["galactic_highway"])
    scene_count = max(4, min(int(scene_count), 180))
    cast = cast_members or DEFAULT_CAST
    valid_char_ids = [c["id"] for c in cast] + ["diagram"]

    if scene_count <= 12:
        num_chapters = max(2, scene_count // 4)
    elif scene_count <= 32:
        num_chapters = max(4, round(scene_count / 6))
    elif scene_count <= 72:
        num_chapters = max(6, round(scene_count / 9))
    else:
        num_chapters = max(8, min(14, round(scene_count / 12)))

    base_per_ch = scene_count // num_chapters
    rem = scene_count % num_chapters
    chapter_scene_counts = [base_per_ch + (1 if i < rem else 0) for i in range(num_chapters)]

    if progress_cb:
        progress_cb(
            f"Planning {num_chapters}-chapter practical breakdown ({scene_count} beats) with {llm_model.split('/')[-1]}...",
            1,
            num_chapters + 2,
        )

    outline_system = f"""You are the writer and creator of the YouTube channel "Galactic Highway" ("Bunker Survival 1 Year", RmyjNoz2pw4).
{GALACTIC_HIGHWAY_WRITING_BIBLE}

Your job in Stage 1 is to plan a {num_chapters}-chapter long-form video for the user's topic.
Structure the chapters like a real Galactic Highway video:
- Escalate chronologically (e.g., Minute 1 / Day 1 -> Setting Up the Core Systems -> The Math of Food/Water/Energy -> Routine & Hidden Maintenance Problems -> Day X Major System Failure & Step-by-Step Repair -> Psychological Strain / External Threat -> Long-Term Endgame).
- Each chapter summary must list the EXACT concrete numbers, physical mechanisms, failure modes, and tools that will be explained in that chapter so chapters never repeat each other.

Return ONLY valid JSON matching this schema:
{{
  "title": "Short, Direct YouTube Title (like 'Bunker Survival 1 Year' or 'Submarine Survival 6 Months')",
  "logline": "One plain, concrete sentence explaining the premise and stakes",
  "chapters": [
    {{
      "chapter_number": 1,
      "title": "Plain 2-4 word chapter title (e.g. 'The disaster strikes', 'Stocking for survival', 'Critical power failure')",
      "summary": "Specific numbers, physical equipment, failure modes, and actions covered in this chapter.",
      "scene_count": 8
    }}
  ]
}}"""

    outline_user = (
        f"USER TOPIC / PROMPT: {topic}\n"
        f"{f'NOTES: {custom_notes}' if custom_notes else ''}\n\n"
        f"Create a {num_chapters}-chapter plan with these exact scene counts per chapter: {chapter_scene_counts} (total = {scene_count} beats)."
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        master_plan = await _call_openrouter_llm(
            client, key, llm_model, outline_system, outline_user, temperature=0.6
        )

        raw_chapters = master_plan.get("chapters") or []
        while len(raw_chapters) < num_chapters:
            idx = len(raw_chapters) + 1
            raw_chapters.append(
                {
                    "chapter_number": idx,
                    "title": f"Part {idx}",
                    "summary": f"Practical mechanics, failure modes, and timeline progression for {topic} (Part {idx}).",
                    "scene_count": chapter_scene_counts[idx - 1],
                }
            )
        raw_chapters = raw_chapters[:num_chapters]
        for i, ch in enumerate(raw_chapters):
            ch["scene_count"] = chapter_scene_counts[i]
            ch["chapter_number"] = i + 1

        video_title = master_plan.get("title") or topic[:70]
        video_logline = master_plan.get("logline") or f"A {scene_count}-beat breakdown of: {topic}"

        outline_context = "\n".join(
            f"Chapter {c['chapter_number']} ({c['title']} - {c['scene_count']} beats): {c.get('summary', '')}"
            for c in raw_chapters
        )

        llm_sem = asyncio.Semaphore(5)
        completed_chapters = 0

        async def _expand_chapter(ch_obj: dict[str, Any]) -> list[dict[str, Any]]:
            nonlocal completed_chapters
            ch_num = ch_obj["chapter_number"]
            ch_title = ch_obj.get("title", f"Chapter {ch_num}")
            ch_summary = ch_obj.get("summary", "")
            target_cnt = int(ch_obj["scene_count"])

            ch_system = f"""You are writing Chapter {ch_num} ("{ch_title}") of the video "{video_title}".
{GALACTIC_HIGHWAY_WRITING_BIBLE}

CHARACTER & DIAGRAM SELECTION (`character_id`):
- Use `"alex"` (the main 2D stick-figure protagonist in the bright orange cap) when "You" are on screen doing something, reacting, or operating gear (~60% of beats).
- Use `"diagram"` (NO character — clean isolated 2D vector props/cutaway/numbers on pure #FFFFFF white background) when listing supplies, showing calorie/gallon math, or showing how a pipe/filter/battery works (~35% of beats).
- Optionally use `"elena"` (yellow hard-hat engineer), `"marcus"` (olive beret official/soldier), `"maya"` (blue cap medic), or `"jonah"` (red beanie scout/stranger) ONLY when a secondary person/specialist/outsider is being shown in that specific beat.
- NEVER mention names like "Alex" or "Elena" in the spoken `narration`! The spoken `narration` is ALWAYS second-person ("You...").

CAMERA MOTION (`camera_motion`):
- Prefer `"static"` or `"zoom_in"` for 85% of beats (just like the real Galactic Highway video). Use `"zoom_out"`, `"pan_right"`, or `"shake"` sparingly.

Return ONLY valid JSON matching this schema:
{{
  "scenes": [
    {{
      "title": "2-4 word beat label",
      "character_id": "alex",
      "narration": "1 to 3 short, deadpan, concrete sentences (14 to 24 words total). Zero flowery adjectives. Plain spoken English with specific numbers or mechanics.",
      "visual_prompt": "Single, uncluttered 2D illustration on a stark pure white (#FFFFFF) background with ONLY 1 to 3 clear objects matching the exact noun in the narration.",
      "label_overlay": "Short bold uppercase text drawn inside the frame (e.g. '6:14', '2,000 GAL', 'MRE', 'DAY 71', 'CO2') or empty string",
      "camera_motion": "static",
      "sfx_cue": "none"
    }}
  ]
}}
Allowed `camera_motion`: ["static", "zoom_in", "zoom_out", "pan_right", "pan_left", "shake"]
Allowed `sfx_cue`: ["none", "siren", "radio_static", "hatch_seal", "geiger", "power_down", "heartbeat", "explosion_rumble", "bunker_hum"]"""

            ch_user = (
                f"TOPIC: {topic}\n"
                f"FULL VIDEO OUTLINE:\n{outline_context}\n\n"
                f"WRITE CHAPTER {ch_num}: \"{ch_title}\"\n"
                f"Chapter Beats to Cover: {ch_summary}\n"
                f"Write EXACTLY {target_cnt} sequential beats. Make every single line sound like the verbatim Galactic Highway transcript—plain, hyper-specific, deadpan, zero AI story slop."
            )

            async with llm_sem:
                res = await _call_openrouter_llm(
                    client, key, llm_model, ch_system, ch_user, temperature=0.6
                )
                scenes_list = res.get("scenes") if isinstance(res, dict) else res
                if not isinstance(scenes_list, list):
                    scenes_list = []

                while len(scenes_list) < target_cnt:
                    scenes_list.append(
                        {
                            "title": f"{ch_title} #{len(scenes_list) + 1}",
                            "character_id": "alex",
                            "narration": "You check the gauges and write down the numbers in the logbook. Nothing gets skipped.",
                            "visual_prompt": "The 2D stick-figure in the bright orange cap writing in a notebook at a simple grey desk on a pure white (#FFFFFF) background.",
                            "label_overlay": "",
                            "camera_motion": "static",
                            "sfx_cue": "none",
                        }
                    )
                scenes_list = scenes_list[:target_cnt]
                for sc in scenes_list:
                    sc["chapter"] = ch_title
                    cid = sc.get("character_id") or ("alex" if sc.get("use_character_ref", True) else "diagram")
                    if cid not in valid_char_ids:
                        cid = "alex"
                    sc["character_id"] = cid
                    sc["use_character_ref"] = cid != "diagram"

                completed_chapters += 1
                if progress_cb:
                    progress_cb(
                        f"Wrote Chapter {ch_num}/{num_chapters}: \"{ch_title}\" ({target_cnt} beats)",
                        completed_chapters + 1,
                        num_chapters + 2,
                    )
                return scenes_list

        expanded_lists = await asyncio.gather(*[_expand_chapter(ch) for ch in raw_chapters])

    all_scenes = []
    chapters_meta = []
    for ch_idx, ch_scenes in enumerate(expanded_lists):
        ch_title = raw_chapters[ch_idx].get("title", f"Chapter {ch_idx + 1}")
        chapters_meta.append(
            {
                "title": ch_title,
                "summary": raw_chapters[ch_idx].get("summary", ""),
                "start_scene_index": len(all_scenes),
                "scene_count": len(ch_scenes),
            }
        )
        for sc in ch_scenes:
            sc["scene_number"] = len(all_scenes) + 1
            all_scenes.append(sc)

    return {
        "title": video_title,
        "logline": video_logline,
        "chapters": chapters_meta,
        "scenes": all_scenes,
    }


def _enhance_and_normalize_image_bytes(
    raw_bytes: bytes,
    aspect_ratio: str = "16:9",
    enhance_line_art: bool = True,
) -> bytes:
    """
    Zero-cost PIL Visual Quality Booster:
    1. Fits to exact 1920x1080 (or 1080x1920).
    2. Normalizes near-white background pixels (>238 across RGB with low chroma) to pure #FFFFFF
       so cuts across a 20-minute video never flicker between off-white and pure white.
    3. Sharpens black ink line-art and diagram typography with an unsharp mask.
    """
    target_w, target_h = (1920, 1080) if aspect_ratio != "9:16" else (1080, 1920)
    with Image.open(io.BytesIO(raw_bytes)) as im:
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[3])
            im = bg
        else:
            im = im.convert("RGB")

        fitted = ImageOps.fit(im, (target_w, target_h), method=Image.Resampling.LANCZOS)

        if enhance_line_art:
            arr = np.array(fitted, dtype=np.uint8)
            # Push near-white low-saturation background pixels to pure #FFFFFF
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            max_c = np.maximum(np.maximum(r, g), b)
            min_c = np.minimum(np.minimum(r, g), b)
            near_white = (min_c >= 236) & ((max_c - min_c) <= 14)
            arr[near_white] = [255, 255, 255]

            # Deepen near-black ink outlines (< 32) toward crisp black
            near_black = max_c <= 32
            arr[near_black] = (arr[near_black] * 0.5).astype(np.uint8)

            fitted = Image.fromarray(arr, mode="RGB")
            fitted = fitted.filter(ImageFilter.UnsharpMask(radius=1.1, percent=125, threshold=3))
            fitted = ImageEnhance.Contrast(fitted).enhance(1.04)

        out_buf = io.BytesIO()
        fitted.save(out_buf, format="PNG", optimize=True)
        return out_buf.getvalue()


async def generate_character_sheet_image(
    character_description: str,
    output_path: Path,
    model: str = "bytedance-seed/seedream-5-0-flash",
) -> dict[str, Any]:
    prompt = (
        "Character reference sheet in the exact 2D minimalist stick-figure drawing style of the reference image "
        "on a stark pure white (#FFFFFF) background. "
        f"{character_description} "
        "Show the full-body 2D stick-figure character standing center-frame on a completely blank pure white (#FFFFFF) background "
        "with thin uniform black stick limbs (#000000), simple round white head, simple cartoon eyes and mouth, "
        "and flat 2D vector coloring on their hat/accessory only. No background furniture, no walls, no clutter."
    )
    base_style_ref = REFERENCE_DIR / "clean_character_anchor.png"
    if not base_style_ref.exists():
        base_style_ref = REFERENCE_DIR / "opening" / "sec_01.jpg"
    return await generate_scene_image(
        prompt=prompt,
        output_path=output_path,
        model=model,
        style_id="galactic_highway",
        aspect_ratio="16:9",
        use_character_ref=True,
        character_ref_path=base_style_ref,
        custom_character_desc=character_description,
    )


async def generate_scene_image(
    prompt: str,
    output_path: Path,
    model: str = "bytedance-seed/seedream-5-0-flash",
    style_id: str = "galactic_highway",
    aspect_ratio: str = "16:9",
    use_character_ref: bool = True,
    character_ref_path: Optional[Path] = None,
    custom_character_desc: Optional[str] = None,
) -> dict[str, Any]:
    key = get_openrouter_api_key()
    if not key:
        raise RuntimeError("OpenRouter API key is not configured.")

    style = STYLE_PRESETS.get(style_id, STYLE_PRESETS["galactic_highway"])
    char_desc = custom_character_desc or style["character_desc"]

    full_prompt_parts = [style["prompt_prefix"]]
    if use_character_ref:
        full_prompt_parts.append(
            "Keep the exact same 2D stick-figure drawing style and character from the reference image: "
            + char_desc
        )
    else:
        full_prompt_parts.append(
            "Clean isolated 2D flat vector explainer diagram/prop scene on a stark pure white (#FFFFFF) background in the exact same black-outline drawing style. "
        )
    full_prompt_parts.append(prompt)
    full_prompt = " ".join(full_prompt_parts)

    default_ref = REFERENCE_DIR / "clean_character_anchor.png"
    if not default_ref.exists():
        default_ref = REFERENCE_DIR / "opening" / "sec_01.jpg"
    ref_candidate = character_ref_path if (character_ref_path and character_ref_path.exists()) else default_ref
    ref_uri = _encode_image_data_uri(ref_candidate) if (ref_candidate and ref_candidate.exists()) else None

    models_to_try = [model]
    for fallback in ["bytedance-seed/seedream-5-0-flash", "google/gemini-nano-banana-2.1"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_err = None
    for current_model in models_to_try:
        payload: dict[str, Any] = {
            "model": current_model,
            "prompt": full_prompt,
            "aspect_ratio": "16:9" if aspect_ratio != "9:16" else "9:16",
        }
        if ref_uri:
            payload["input_references"] = [
                {"type": "image_url", "image_url": {"url": ref_uri}}
            ]

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/images",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code != 200 and "input_references" in payload:
                    payload.pop("input_references", None)
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/images",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:250]}"
                    continue

                res = resp.json()
                b64_data = res["data"][0]["b64_json"]
                raw_bytes = base64.b64decode(b64_data)
                normalized_png = await asyncio.to_thread(
                    _enhance_and_normalize_image_bytes,
                    raw_bytes,
                    aspect_ratio,
                    True,
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(normalized_png)
                usage = res.get("usage", {})
                return {
                    "model_used": current_model,
                    "cost": usage.get("cost", 0.0),
                    "bytes": len(normalized_png),
                }
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(f"Image generation failed across models. Last error: {last_err}")


def probe_audio_duration(audio_path: Path) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            stderr=subprocess.STDOUT,
        ).decode("utf-8").strip()
        return max(1.0, round(float(out), 2))
    except Exception:
        return 5.5


def _master_voice_with_studio_mic_eq(input_audio_path: Path, output_mp3_path: Path, is_raw_pcm: bool = False) -> None:
    """
    Applies a subtle Shure SM7B broadcast condenser microphone mastering chain:
    - 70Hz high-pass filter
    - +2.0dB warm chest presence at 165Hz
    - -2.2dB de-essing / digital harshness cut at 4200Hz
    - Gentle 2:1 broadcast leveling compressor so the voice sounds warm, intimate, and human.
    """
    af_chain = (
        "highpass=f=70,"
        "equalizer=f=165:t=q:w=1.1:g=2.0,"
        "equalizer=f=4200:t=q:w=1.6:g=-2.2,"
        "acompressor=threshold=-19dB:ratio=2.0:attack=18:release=200:makeup=1.5dB"
    )
    cmd = ["ffmpeg", "-y"]
    if is_raw_pcm:
        cmd += ["-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(input_audio_path)]
    else:
        cmd += ["-i", str(input_audio_path)]
    cmd += [
        "-af",
        af_chain,
        "-ar",
        "44100",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_mp3_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def generate_scene_speech(
    text: str,
    output_path: Path,
    tts_model: str = "microsoft/mai-voice-2.1",
    voice: str = "en-US-Grant:MAI-Voice-2.1",
    voice_clone_sample: Optional[Path] = None,
    instructions: str = (
        "Speak like a real, grounded, late-night human documentary storyteller close to a warm studio microphone. "
        "Use natural conversational pacing, subtle human breaths, and relaxed micro-pauses on punctuation. "
        "Never sound robotic or like an AI announcer."
    ),
) -> dict[str, Any]:
    key = get_openrouter_api_key()
    if not key:
        raise RuntimeError("OpenRouter API key is not configured.")

    cleaned_text = re.sub(r"\[.*?\]", "", text).strip()
    if not cleaned_text:
        cleaned_text = "..."

    output_path.parent.mkdir(parents=True, exist_ok=True)

    attempts = [
        (tts_model, voice),
        ("microsoft/mai-voice-2.1", "en-US-Grant:MAI-Voice-2.1"),
        ("google/gemini-3.8-flash-tts", "Charon"),
        ("elevenlabs/eleven-v3-conversational", "chris"),
    ]

    last_err = None
    for cur_model, cur_voice in attempts:
        is_gemini_pcm = "gemini" in cur_model.lower()
        is_clone = cur_model.startswith("fish-audio/") or cur_voice == "clone_reference"

        payload: dict[str, Any] = {
            "model": cur_model
            if not (cur_voice == "clone_reference" and not cur_model.startswith("fish-audio/"))
            else "fish-audio/s2.1-pro",
            "input": cleaned_text,
            "response_format": "pcm" if is_gemini_pcm else "mp3",
        }

        if is_clone:
            sample_file = voice_clone_sample or (REFERENCE_DIR / "narrator_sample.wav")
            if sample_file.exists():
                b64_wav = base64.b64encode(sample_file.read_bytes()).decode("ascii")
                mime = "audio/wav" if sample_file.suffix.lower() == ".wav" else "audio/mpeg"
                payload["input_references"] = [
                    {"type": "input_audio", "input_audio": {"data": f"data:{mime};base64,{b64_wav}"}},
                    {
                        "type": "text",
                        "text": (
                            "You've prepared for years. Food, water, air, power, everything you need "
                            "except knowing what's up there. The lights come on. The air system hums to life."
                        ),
                    },
                ]
            else:
                payload["model"] = "microsoft/mai-voice-2.1"
                payload["voice"] = "en-US-Grant:MAI-Voice-2.1"
        else:
            payload["voice"] = cur_voice
            if is_gemini_pcm and instructions:
                payload["instructions"] = instructions

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:250]}"
                    continue

                raw_audio = resp.content
                raw_tmp = output_path.with_suffix(".raw_in")
                raw_tmp.write_bytes(raw_audio)
                await asyncio.to_thread(
                    _master_voice_with_studio_mic_eq,
                    raw_tmp,
                    output_path,
                    is_gemini_pcm,
                )
                raw_tmp.unlink(missing_ok=True)

                duration = await asyncio.to_thread(probe_audio_duration, output_path)
                return {
                    "model_used": payload["model"],
                    "voice_used": cur_voice,
                    "duration": duration,
                    "bytes": output_path.stat().st_size,
                }
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(f"TTS generation failed: {last_err}")
