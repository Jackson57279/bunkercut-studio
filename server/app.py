import asyncio
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any
from aiohttp import web

from .config import (
    BASE_DIR,
    CAST_DIR,
    PROJECTS_DIR,
    REFERENCE_DIR,
    SFX_DIR,
    get_key_status,
    set_runtime_api_key,
)
from .openrouter import (
    DEFAULT_CAST,
    DURATION_PRESETS,
    FEATURED_HUMAN_VOICES,
    IMAGE_MODELS,
    LLM_MODELS,
    STYLE_PRESETS,
    TTS_MODELS,
    VISUAL_DENSITY_MODES,
    generate_character_sheet_image,
    generate_scene_image,
    generate_scene_speech,
    generate_storyboard_script,
)
from .renderer import render_project_video
from .sfx import ensure_sfx_file

ACTIVE_JOBS: dict[str, dict[str, Any]] = {}
CANCEL_FLAGS: set[str] = set()
CUSTOM_CAST_FILE = CAST_DIR / "custom_cast.json"

STARTER_TEMPLATES = [
    {
        "id": "submarine_180_days",
        "category": "Deep Sea & Systems",
        "title": "Submarine Survival 6 Months",
        "topic": "How you survive 6 months sealed inside a nuclear submarine 800 feet underwater without surfacing: splitting seawater for oxygen, scrubbing carbon dioxide before it poisons the air, 18-hour watch schedules without sunlight, fixing a high-pressure saltwater pipe leak at depth, and what happens when the sonar picks up something outside the hull.",
        "scene_count": 64,
    },
    {
        "id": "antarctic_winter_over",
        "category": "Extreme Isolation",
        "title": "Antarctic Station Survival 9 Months",
        "topic": "How to survive 9 months of total winter darkness at an inland Antarctic station when temperatures drop to -85°F and no plane can land: melting snow for every gallon of water, keeping the diesel generators from gelling, static electricity hazards, rationing hydroponic greens, dental and appendix emergencies with no hospital, and when the main heating boiler fails in Month 5.",
        "scene_count": 64,
    },
    {
        "id": "grid_collapse_365",
        "category": "Infrastructure Breakdown",
        "title": "Grid Collapse Survival 1 Year",
        "topic": "How to survive 1 year when the power grid goes down and never comes back: filling bathtubs and water heaters in the first 4 hours before municipal pressure drops, why gasoline goes bad in 90 days, curing and canning food before freezers thaw, gravity-fed rainwater filtration, wood-stove heating math, and staying invisible when neighbors run out of food in Week 3.",
        "scene_count": 96,
    },
    {
        "id": "deep_sea_saturation",
        "category": "Extreme Jobs",
        "title": "Saturation Diver Survival 28 Days",
        "topic": "How saturation divers live for 28 days inside a steel chamber pressurized to 1,000 feet of seawater: breathing heliox gas that turns your voice high-pitched, why opening the hatch would kill you in two seconds, flushing toilets under extreme pressure, food passed through medical locks, working in pitch-black freezing water on the seafloor, and what happens if the umbilical line seizes.",
        "scene_count": 64,
    },
    {
        "id": "mars_lava_tube_500",
        "category": "Off-World Survival",
        "title": "Mars Habitat Survival 500 Days",
        "topic": "How to survive 500 days sealed in an underground Martian lava tube waiting for a rescue window: baking water out of frozen soil, washing toxic perchlorates out of the dirt to grow potatoes, why fine Martian dust destroys airlock seals and lungs, recycling 98% of urine and sweat, and patching a pressure leak in 4 minutes.",
        "scene_count": 96,
    },
    {
        "id": "missile_silo_5_years",
        "category": "Underground Shelter",
        "title": "Missile Silo Survival 5 Years",
        "topic": "How to survive 5 years inside a 174-foot-deep decommissioned Atlas missile silo: sealing the 45-ton blast doors, pumping groundwater from a deep well, running geothermal cooling loops, raising tilapia in basement tanks, fighting underground humidity and black mold, and what happens on Day 412 when the primary water pump burns out.",
        "scene_count": 96,
    },
]


def _get_all_cast() -> list[dict[str, Any]]:
    cast = [dict(c) for c in DEFAULT_CAST]
    if CUSTOM_CAST_FILE.exists():
        try:
            extra = json.loads(CUSTOM_CAST_FILE.read_text())
            if isinstance(extra, list):
                cast.extend(extra)
        except Exception:
            pass
    for c in cast:
        rfile = Path(c.get("reference_file", ""))
        if rfile.exists():
            c["ready"] = True
            c["reference_url"] = f"{c['reference_url'].split('?')[0]}?t={int(rfile.stat().st_mtime)}"
        else:
            c["ready"] = False
            c["reference_url"] = "/media/reference/clean_character_anchor.png"
    return cast


def _project_path(project_id: str) -> Path:
    safe_id = "".join(c for c in project_id if c.isalnum() or c in ("-", "_"))
    return PROJECTS_DIR / safe_id


def _load_project(project_id: str) -> dict[str, Any]:
    pdir = _project_path(project_id)
    meta_file = pdir / "project.json"
    if not meta_file.exists():
        raise web.HTTPNotFound(text=json.dumps({"error": f"Project {project_id} not found"}))
    return json.loads(meta_file.read_text())


def _save_project(project: dict[str, Any]) -> dict[str, Any]:
    project["updated_at"] = int(time.time())
    pdir = _project_path(project["id"])
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "scenes").mkdir(parents=True, exist_ok=True)
    (pdir / "project.json").write_text(json.dumps(project, indent=2))
    return project


def _decorate_project_urls(project: dict[str, Any]) -> dict[str, Any]:
    pid = project["id"]
    pdir = _project_path(pid)
    ts = project.get("updated_at", int(time.time()))
    out = json.loads(json.dumps(project))

    settings = out.setdefault("settings", {})
    settings.setdefault("visual_density", "smart_2x")
    settings.setdefault("include_chapter_cards", True)

    char_ref = settings.get("character_ref_file")
    if char_ref and (pdir / char_ref).exists():
        out["character_ref_url"] = (
            f"/media/projects/{pid}/{char_ref}?t={int((pdir / char_ref).stat().st_mtime)}"
        )
    else:
        out["character_ref_url"] = "/media/reference/clean_character_anchor.png"

    if out.get("video_file") and (pdir / out["video_file"]).exists():
        out["video_url"] = (
            f"/media/projects/{pid}/{out['video_file']}?t={int((pdir / out['video_file']).stat().st_mtime)}"
        )
    else:
        out["video_url"] = None

    if out.get("srt_file") and (pdir / out["srt_file"]).exists():
        out["srt_url"] = f"/media/projects/{pid}/{out['srt_file']}?t={ts}"
    else:
        out["srt_url"] = None

    ready_images = 0
    ready_audios = 0
    est_duration = 0.0
    unique_images_set = set()

    for sc in out.get("scenes", []):
        sid = sc["id"]
        sc.setdefault("character_id", "alex" if sc.get("use_character_ref", True) else "diagram")
        sc.setdefault("shot_variant", "wide")
        img_rel = sc.get("image_file") or f"scenes/{sid}.png"
        aud_rel = sc.get("audio_file") or f"scenes/{sid}.mp3"
        clip_rel = sc.get("clip_file") or f"scenes/{sid}_clip.mp4"

        img_p = pdir / img_rel
        aud_p = pdir / aud_rel
        clip_p = pdir / clip_rel

        if img_p.exists():
            sc["image_url"] = f"/media/projects/{pid}/{img_rel}?t={int(img_p.stat().st_mtime)}"
            ready_images += 1
            unique_images_set.add(img_rel)
        else:
            sc["image_url"] = None

        if aud_p.exists():
            sc["audio_url"] = f"/media/projects/{pid}/{aud_rel}?t={int(aud_p.stat().st_mtime)}"
            ready_audios += 1
        else:
            sc["audio_url"] = None

        sc["clip_url"] = (
            f"/media/projects/{pid}/{clip_rel}?t={int(clip_p.stat().st_mtime)}"
            if clip_p.exists()
            else None
        )
        est_duration += float(sc.get("duration") or 6.5)

    out["stats"] = {
        "total_scenes": len(out.get("scenes", [])),
        "ready_images": ready_images,
        "unique_images": len(unique_images_set),
        "ready_audios": ready_audios,
        "estimated_duration_sec": round(est_duration, 1),
    }
    out["active_job"] = ACTIVE_JOBS.get(pid)
    return out


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as ex:
            resp = ex
        except Exception as e:
            resp = web.json_response({"error": str(e)}, status=500)

    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


def _get_featured_voices_with_urls() -> list[dict[str, Any]]:
    out = []
    for fv in FEATURED_HUMAN_VOICES:
        item = dict(fv)
        safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{fv['tts_model']}_{fv['voice']}")
        cached = SFX_DIR / f"preview_{safe_slug}.mp3"
        if cached.exists():
            item["preview_url"] = f"/media/projects/_sfx_cache/{cached.name}?t={int(cached.stat().st_mtime)}"
        else:
            item["preview_url"] = None
        out.append(item)
    return out


async def handle_status(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "api_key": get_key_status(),
            "cast": _get_all_cast(),
            "featured_voices": _get_featured_voices_with_urls(),
            "duration_presets": DURATION_PRESETS,
            "visual_density_modes": VISUAL_DENSITY_MODES,
            "image_models": IMAGE_MODELS,
            "tts_models": TTS_MODELS,
            "llm_models": LLM_MODELS,
            "style_presets": list(STYLE_PRESETS.values()),
            "starter_templates": STARTER_TEMPLATES,
            "sfx_cues": [
                {"id": "none", "name": "No SFX"},
                {"id": "siren", "name": "Civil Defense Siren Wail"},
                {"id": "radio_static", "name": "Emergency Radio Static"},
                {"id": "hatch_seal", "name": "Steel Hatch Slam & Lock"},
                {"id": "geiger", "name": "Geiger Counter Clicks"},
                {"id": "power_down", "name": "Grid Power Failure Whine"},
                {"id": "heartbeat", "name": "Tense Heartbeat Pulse"},
                {"id": "explosion_rumble", "name": "Distant Shockwave Rumble"},
                {"id": "bunker_hum", "name": "Air Filtration System Hum"},
            ],
            "camera_motions": [
                {"id": "zoom_in", "name": "Slow Push In (Ken Burns)"},
                {"id": "zoom_out", "name": "Slow Pull Out"},
                {"id": "pan_right", "name": "Pan Left → Right"},
                {"id": "pan_left", "name": "Pan Right → Left"},
                {"id": "shake", "name": "Emergency Camera Shake"},
                {"id": "static", "name": "Crisp Static Cut"},
            ],
        }
    )


async def handle_update_key(request: web.Request) -> web.Response:
    body = await request.json()
    key = (body.get("api_key") or "").strip()
    if not key:
        return web.json_response({"error": "API key cannot be empty"}, status=400)
    set_runtime_api_key(key)
    return web.json_response({"api_key": get_key_status()})


async def handle_create_or_generate_cast_member(request: web.Request) -> web.Response:
    body = await request.json()
    cid = re.sub(r"[^a-z0-9_]", "_", (body.get("id") or body.get("name") or "char").lower().strip())[:24]
    if not cid:
        cid = f"char_{uuid.uuid4().hex[:6]}"

    all_cast = _get_all_cast()
    existing = next((c for c in all_cast if c["id"] == cid), None)

    name = (body.get("name") or (existing["name"] if existing else "New Character")).strip()
    role = (body.get("role") or (existing.get("role", "Specialist") if existing else "Specialist")).strip()
    badge = (body.get("badge") or (existing.get("badge", "Custom") if existing else "Custom")).strip()
    visual_desc = (
        body.get("visual_description")
        or (existing["visual_description"] if existing else DEFAULT_CAST[0]["visual_description"])
    ).strip()
    default_voice = body.get("default_voice") or (existing.get("default_voice", "am_adam") if existing else "am_adam")

    out_file = CAST_DIR / f"char_{cid}.png"
    await generate_character_sheet_image(
        character_description=visual_desc,
        output_path=out_file,
        model=body.get("image_model", "bytedance-seed/seedream-5-0-flash"),
    )

    if not any(d["id"] == cid for d in DEFAULT_CAST):
        custom_list = []
        if CUSTOM_CAST_FILE.exists():
            try:
                custom_list = json.loads(CUSTOM_CAST_FILE.read_text())
            except Exception:
                custom_list = []
        custom_list = [c for c in custom_list if c.get("id") != cid]
        custom_list.append(
            {
                "id": cid,
                "name": name,
                "role": role,
                "badge": badge,
                "accent": body.get("accent", "#6366F1"),
                "default_voice": default_voice,
                "visual_description": visual_desc,
                "reference_url": f"/media/reference/cast/char_{cid}.png",
                "reference_file": str(out_file),
            }
        )
        CUSTOM_CAST_FILE.write_text(json.dumps(custom_list, indent=2))

    return web.json_response({"cast": _get_all_cast()})


async def handle_reference_info(request: web.Request) -> web.Response:
    info_path = REFERENCE_DIR / "RmyjNoz2pw4.info.json"
    transcript_path = REFERENCE_DIR / "transcript.txt"
    info_data = {}
    if info_path.exists():
        raw = json.loads(info_path.read_text())
        info_data = {
            "id": raw.get("id", "RmyjNoz2pw4"),
            "title": raw.get("title", "Bunker Survival 1 Year"),
            "channel": raw.get("channel", "Galactic Highway"),
            "duration": raw.get("duration", 691),
            "duration_string": raw.get("duration_string", "11:31"),
            "resolution": f"{raw.get('width', 1920)}x{raw.get('height', 1080)}",
            "fps": raw.get("fps", 30),
            "description": raw.get("description", ""),
            "chapters": raw.get("chapters", []),
            "video_url": "/media/reference/RmyjNoz2pw4.webm",
            "narrator_sample_url": "/media/reference/narrator_sample.wav",
        }

    opening_frames = sorted((REFERENCE_DIR / "opening").glob("sec_*.jpg"))
    overview_frames = sorted((REFERENCE_DIR / "frames").glob("frame_*.jpg"))

    transcript_lines = []
    if transcript_path.exists():
        transcript_lines = transcript_path.read_text().splitlines()[:100]

    return web.json_response(
        {
            "reference": info_data,
            "opening_frames": [f"/media/reference/opening/{p.name}" for p in opening_frames],
            "overview_frames": [f"/media/reference/frames/{p.name}" for p in overview_frames],
            "transcript_preview": transcript_lines,
            "pacing_stats": {
                "total_cuts": 130,
                "avg_shot_seconds": 5.3,
                "median_shot_seconds": 5.0,
                "visual_style": "2D Stick-Figure Line Art on Pure White (#FFFFFF) + Flat Vector Props",
            },
        }
    )


async def handle_download_youtube_ref(request: web.Request) -> web.Response:
    body = await request.json()
    url = (body.get("url") or "").strip()
    if not url.startswith("http"):
        return web.json_response({"error": "Valid YouTube URL required"}, status=400)

    custom_dir = REFERENCE_DIR / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--ignore-errors",
        "--js-runtimes",
        "node",
        "--write-info-json",
        "-o",
        str(custom_dir / "%(id)s.%(ext)s"),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return web.json_response(
            {"error": f"yt-dlp failed: {stdout.decode('utf-8', errors='ignore')[-300:]}"},
            status=400,
        )

    info_files = sorted(custom_dir.glob("*.info.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not info_files:
        return web.json_response({"error": "No metadata produced"}, status=400)

    latest_info = json.loads(info_files[0].read_text())
    vid_id = latest_info.get("id")
    vid_candidates = [
        p
        for p in custom_dir.glob(f"{vid_id}.*")
        if p.suffix.lower() in (".mp4", ".webm", ".mkv")
    ]
    vid_url = f"/media/reference/custom/{vid_candidates[0].name}" if vid_candidates else None
    return web.json_response(
        {
            "id": vid_id,
            "title": latest_info.get("title"),
            "channel": latest_info.get("channel"),
            "duration": latest_info.get("duration"),
            "chapters": latest_info.get("chapters", []),
            "video_url": vid_url,
        }
    )


async def handle_list_projects(request: web.Request) -> web.Response:
    projects = []
    for pdir in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if pdir.is_dir() and not pdir.name.startswith("_"):
            meta = pdir / "project.json"
            if meta.exists():
                try:
                    data = json.loads(meta.read_text())
                    projects.append(_decorate_project_urls(data))
                except Exception:
                    pass
    return web.json_response({"projects": projects})


async def handle_create_project(request: web.Request) -> web.Response:
    body = await request.json()
    pid = f"proj_{uuid.uuid4().hex[:8]}"
    title = (body.get("title") or "Untitled Long-Form Video").strip()
    topic = (body.get("topic") or title).strip()
    settings = body.get("settings") or {}

    project = {
        "id": pid,
        "title": title,
        "logline": body.get("logline", ""),
        "topic": topic,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "settings": {
            "style_id": settings.get("style_id", "galactic_highway"),
            "image_model": settings.get("image_model", "bytedance-seed/seedream-5-0-flash"),
            "tts_model": settings.get("tts_model", "microsoft/mai-voice-2.1"),
            "tts_voice": settings.get("tts_voice", "en-US-Grant:MAI-Voice-2.1"),
            "llm_model": settings.get("llm_model", "anthropic/claude-sonnet-5.5"),
            "visual_density": settings.get("visual_density", "smart_2x"),
            "aspect_ratio": settings.get("aspect_ratio", "16:9"),
            "caption_style": settings.get("caption_style", "none"),
            "include_sfx": settings.get("include_sfx", True),
            "include_ambient": settings.get("include_ambient", True),
            "include_chapter_cards": settings.get("include_chapter_cards", False),
        },
        "chapters": body.get("chapters", []),
        "scenes": body.get("scenes", []),
        "video_file": None,
        "srt_file": None,
        "total_duration": 0.0,
    }
    _save_project(project)
    return web.json_response({"project": _decorate_project_urls(project)})


async def handle_get_project(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    project = _load_project(pid)
    return web.json_response({"project": _decorate_project_urls(project)})


async def handle_update_project(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    project = _load_project(pid)
    body = await request.json()

    for key in ["title", "logline", "topic", "chapters", "scenes"]:
        if key in body:
            project[key] = body[key]
    if "settings" in body and isinstance(body["settings"], dict):
        project["settings"].update(body["settings"])

    _save_project(project)
    return web.json_response({"project": _decorate_project_urls(project)})


async def handle_delete_project(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    CANCEL_FLAGS.add(pid)
    pdir = _project_path(pid)
    if pdir.exists():
        shutil.rmtree(pdir)
    return web.json_response({"deleted": pid})


def _resolve_scene_character_info(character_id: str) -> tuple[Optional[Path], Optional[str], bool]:
    if not character_id or character_id == "diagram":
        return (REFERENCE_DIR / "clean_character_anchor.png", None, False)

    all_cast = _get_all_cast()
    member = next((c for c in all_cast if c["id"] == character_id), None)
    if not member:
        member = DEFAULT_CAST[0]

    ref_file = Path(member.get("reference_file", ""))
    if not ref_file.exists():
        ref_file = REFERENCE_DIR / "clean_character_anchor.png"
    return (ref_file, member["visual_description"], True)


async def _populate_project_script(
    project: dict[str, Any],
    topic: str,
    scene_count: int,
    custom_notes: str = "",
) -> dict[str, Any]:
    pid = project["id"]
    settings = project.get("settings", {})
    all_cast = _get_all_cast()

    def _progress(detail: str, done: int, total: int):
        ACTIVE_JOBS[pid] = {
            "status": "running",
            "stage": "scripting",
            "detail": detail,
            "completed": done,
            "total": total,
            "percent": int(round((done / max(1, total)) * 100)),
        }

    script_data = await generate_storyboard_script(
        topic=topic,
        scene_count=scene_count,
        style_id=settings.get("style_id", "galactic_highway"),
        llm_model=settings.get("llm_model", "anthropic/claude-sonnet-5.5"),
        cast_members=all_cast,
        custom_notes=custom_notes,
        progress_cb=_progress,
    )

    project["title"] = script_data.get("title") or project["title"]
    project["logline"] = script_data.get("logline") or ""
    project["topic"] = topic
    project["chapters"] = script_data.get("chapters") or []

    new_scenes = []
    for idx, sc in enumerate(script_data.get("scenes", [])):
        sid = f"scene_{idx + 1:03d}_{uuid.uuid4().hex[:4]}"
        cid = sc.get("character_id", "alex")
        new_scenes.append(
            {
                "id": sid,
                "scene_number": idx + 1,
                "chapter": sc.get("chapter", "Chapter 1"),
                "title": sc.get("title", f"Scene {idx + 1}"),
                "character_id": cid,
                "use_character_ref": cid != "diagram",
                "shot_variant": "wide",
                "narration": sc.get("narration", ""),
                "visual_prompt": sc.get("visual_prompt", ""),
                "label_overlay": sc.get("label_overlay", ""),
                "camera_motion": sc.get("camera_motion", "zoom_in"),
                "sfx_cue": sc.get("sfx_cue", "none"),
                "image_file": None,
                "audio_file": None,
                "clip_file": None,
                "duration": 6.5,
            }
        )

    project["scenes"] = new_scenes
    project["video_file"] = None
    _save_project(project)
    return project


async def handle_generate_script(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    project = _load_project(pid)
    body = await request.json() if request.can_read_body else {}

    topic = (body.get("topic") or project.get("topic") or project.get("title")).strip()
    scene_count = int(body.get("scene_count") or 42)
    custom_notes = (body.get("custom_notes") or "").strip()
    if "settings" in body and isinstance(body["settings"], dict):
        project["settings"].update(body["settings"])

    try:
        await _populate_project_script(project, topic, scene_count, custom_notes)
        ACTIVE_JOBS.pop(pid, None)
        return web.json_response({"project": _decorate_project_urls(project)})
    except Exception as e:
        ACTIVE_JOBS[pid] = {
            "status": "error",
            "stage": "scripting",
            "detail": str(e),
            "completed": 0,
            "total": 1,
            "percent": 0,
        }
        raise


async def handle_generate_scene_image(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    sid = request.match_info["scene_id"]
    project = _load_project(pid)
    pdir = _project_path(pid)
    body = await request.json() if request.can_read_body else {}

    target_scene = next((s for s in project.get("scenes", []) if s["id"] == sid), None)
    if not target_scene:
        return web.json_response({"error": "Scene not found"}, status=404)

    for k in [
        "visual_prompt",
        "narration",
        "character_id",
        "use_character_ref",
        "camera_motion",
        "sfx_cue",
        "title",
        "label_overlay",
    ]:
        if k in body:
            target_scene[k] = body[k]

    settings = project.get("settings", {})
    img_rel = f"scenes/{sid}.png"
    img_path = pdir / img_rel
    cid = target_scene.get("character_id", "alex")
    ref_path, char_desc, use_ref = _resolve_scene_character_info(cid)

    prompt = target_scene["visual_prompt"]
    if target_scene.get("label_overlay"):
        prompt += f" Include clear bold uppercase sans-serif label text reading '{target_scene['label_overlay']}'."

    gen_info = await generate_scene_image(
        prompt=prompt,
        output_path=img_path,
        model=body.get("image_model") or settings.get("image_model", "bytedance-seed/seedream-5-0-flash"),
        style_id=settings.get("style_id", "galactic_highway"),
        aspect_ratio=settings.get("aspect_ratio", "16:9"),
        use_character_ref=use_ref,
        character_ref_path=ref_path,
        custom_character_desc=char_desc,
    )

    target_scene["image_file"] = img_rel
    target_scene["shot_variant"] = "wide"
    target_scene["last_image_model"] = gen_info["model_used"]
    _save_project(project)
    return web.json_response({"project": _decorate_project_urls(project), "generation": gen_info})


async def handle_generate_scene_audio(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    sid = request.match_info["scene_id"]
    project = _load_project(pid)
    pdir = _project_path(pid)
    body = await request.json() if request.can_read_body else {}

    target_scene = next((s for s in project.get("scenes", []) if s["id"] == sid), None)
    if not target_scene:
        return web.json_response({"error": "Scene not found"}, status=404)

    if "narration" in body:
        target_scene["narration"] = body["narration"]

    settings = project.get("settings", {})
    aud_rel = f"scenes/{sid}.mp3"
    aud_path = pdir / aud_rel

    gen_info = await generate_scene_speech(
        text=target_scene["narration"],
        output_path=aud_path,
        tts_model=body.get("tts_model") or settings.get("tts_model", "microsoft/mai-voice-2.1"),
        voice=body.get("tts_voice") or settings.get("tts_voice", "en-US-Grant:MAI-Voice-2.1"),
    )

    target_scene["audio_file"] = aud_rel
    target_scene["duration"] = round(gen_info["duration"] + 0.30, 2)
    target_scene["last_tts_model"] = gen_info["model_used"]
    _save_project(project)
    return web.json_response({"project": _decorate_project_urls(project), "generation": gen_info})


async def _run_full_production_job(
    pid: str,
    force_regenerate: bool = False,
    generate_script_first: bool = False,
    script_topic: str = "",
    script_scene_count: int = 42,
) -> None:
    CANCEL_FLAGS.discard(pid)
    try:
        project = _load_project(pid)
        pdir = _project_path(pid)

        if generate_script_first:
            await _populate_project_script(
                project,
                topic=script_topic or project.get("topic") or project.get("title"),
                scene_count=script_scene_count,
            )

        if pid in CANCEL_FLAGS:
            ACTIVE_JOBS[pid] = {
                "status": "completed",
                "stage": "paused",
                "detail": "Production paused by user. All completed assets are saved.",
                "completed": 0,
                "total": 1,
                "percent": 0,
            }
            return

        settings = project.get("settings", {})
        visual_density = settings.get("visual_density", "smart_2x")
        divisor = 2 if visual_density == "smart_2x" else (3 if visual_density == "smart_3x" else 1)

        scenes = project.get("scenes", [])
        # Group scenes into master image groups based on visual_density (within the same chapter)
        master_groups: list[list[dict[str, Any]]] = []
        cur_group: list[dict[str, Any]] = []
        for sc in scenes:
            if not cur_group:
                cur_group.append(sc)
            else:
                same_chapter = sc.get("chapter") == cur_group[0].get("chapter")
                if same_chapter and len(cur_group) < divisor:
                    cur_group.append(sc)
                else:
                    master_groups.append(cur_group)
                    cur_group = [sc]
        if cur_group:
            master_groups.append(cur_group)

        total_steps = len(scenes) + len(master_groups) + 2
        completed_steps = 0
        save_lock = asyncio.Lock()

        def _update_job(stage: str, detail: str):
            ACTIVE_JOBS[pid] = {
                "status": "running",
                "stage": stage,
                "detail": detail,
                "completed": completed_steps,
                "total": total_steps,
                "percent": min(99, int(round((completed_steps / max(1, total_steps)) * 100))),
            }

        _update_job(
            "starting",
            f"Producing {len(scenes)} beats ({len(master_groups)} unique illustrations in {visual_density} mode)...",
        )

        tts_sem = asyncio.Semaphore(6)
        img_sem = asyncio.Semaphore(5)

        async def _process_voice(sc: dict[str, Any]):
            nonlocal completed_steps
            if pid in CANCEL_FLAGS:
                return
            sid = sc["id"]
            snum = sc.get("scene_number", 1)
            aud_rel = sc.get("audio_file") or f"scenes/{sid}.mp3"
            aud_path = pdir / aud_rel
            if force_regenerate or not aud_path.exists():
                async with tts_sem:
                    if pid in CANCEL_FLAGS:
                        return
                    _update_job("voiceover", f"Voiceover Beat {snum}/{len(scenes)}: \"{sc.get('title', '')}\"")
                    aud_info = await generate_scene_speech(
                        text=sc["narration"],
                        output_path=aud_path,
                        tts_model=settings.get("tts_model", "microsoft/mai-voice-2.1"),
                        voice=settings.get("tts_voice", "en-US-Grant:MAI-Voice-2.1"),
                    )
                    sc["audio_file"] = aud_rel
                    sc["duration"] = round(aud_info["duration"] + 0.30, 2)
                    async with save_lock:
                        _save_project(project)
            else:
                sc["audio_file"] = aud_rel
            completed_steps += 1
            _update_job("voiceover", f"Voiceover {completed_steps}/{total_steps} ready")

        async def _process_image_group(group: list[dict[str, Any]], g_idx: int):
            nonlocal completed_steps
            if pid in CANCEL_FLAGS:
                return
            lead_sc = group[0]
            lead_sid = lead_sc["id"]
            img_rel = f"scenes/{lead_sid}.png"
            img_path = pdir / img_rel

            if force_regenerate or not img_path.exists():
                async with img_sem:
                    if pid in CANCEL_FLAGS:
                        return
                    _update_job(
                        "images",
                        f"Drawing Master Frame {g_idx + 1}/{len(master_groups)} (covers Beats {group[0]['scene_number']}–{group[-1]['scene_number']})",
                    )
                    cid = lead_sc.get("character_id", "alex")
                    ref_path, char_desc, use_ref = _resolve_scene_character_info(cid)

                    # Always keep the image prompt as a single, uncluttered Galactic Highway drawing!
                    clean_prompt = lead_sc["visual_prompt"]
                    if lead_sc.get("label_overlay"):
                        clean_prompt += f" Include clear bold uppercase sans-serif label text reading '{lead_sc['label_overlay']}'."

                    await generate_scene_image(
                        prompt=clean_prompt,
                        output_path=img_path,
                        model=settings.get("image_model", "bytedance-seed/seedream-5-0-flash"),
                        style_id=settings.get("style_id", "galactic_highway"),
                        aspect_ratio=settings.get("aspect_ratio", "16:9"),
                        use_character_ref=use_ref,
                        character_ref_path=ref_path,
                        custom_character_desc=char_desc,
                    )

            shot_variants = ["wide", "punch_in", "focus_right"]
            for idx_in_g, sc in enumerate(group):
                sc["image_file"] = img_rel
                sc["shot_variant"] = shot_variants[idx_in_g % len(shot_variants)] if len(group) > 1 else "wide"

            async with save_lock:
                _save_project(project)
            completed_steps += 1
            _update_job("images", f"Master Frame {g_idx + 1}/{len(master_groups)} ready.")

        await asyncio.gather(
            *[_process_voice(sc) for sc in scenes],
            *[_process_image_group(g, idx) for idx, g in enumerate(master_groups)],
        )

        if pid in CANCEL_FLAGS:
            ACTIVE_JOBS[pid] = {
                "status": "completed",
                "stage": "paused",
                "detail": "Production paused. Click 'Resume Production' anytime to continue.",
                "completed": completed_steps,
                "total": total_steps,
                "percent": int(round((completed_steps / max(1, total_steps)) * 100)),
            }
            return

        def _render_prog(detail: str, done: int, total: int):
            ACTIVE_JOBS[pid] = {
                "status": "running",
                "stage": "rendering",
                "detail": detail,
                "completed": completed_steps + 1,
                "total": total_steps,
                "percent": min(99, 90 + int(round((done / max(1, total)) * 9))),
            }

        _update_job("rendering", f"Assembling {len(scenes)}-beat 1080p long-form MP4...")
        render_res = await render_project_video(project, pdir, progress_cb=_render_prog)
        project["video_file"] = render_res["video_file"]
        project["srt_file"] = render_res["srt_file"]
        project["chapters_file"] = render_res["chapters_file"]
        project["chapters_text"] = render_res["chapters_text"]
        project["total_duration"] = render_res["total_duration"]
        _save_project(project)

        ACTIVE_JOBS[pid] = {
            "status": "completed",
            "stage": "done",
            "detail": f"Master video rendered ({render_res['total_duration']}s · {len(scenes)} beats · {len(master_groups)} unique frames)",
            "completed": total_steps,
            "total": total_steps,
            "percent": 100,
        }
    except Exception as e:
        ACTIVE_JOBS[pid] = {
            "status": "error",
            "stage": "failed",
            "detail": str(e),
            "completed": 0,
            "total": 1,
            "percent": 0,
        }


async def handle_create_from_prompt(request: web.Request) -> web.Response:
    body = await request.json()
    prompt = (body.get("prompt") or body.get("topic") or "").strip()
    if not prompt:
        return web.json_response({"error": "Please enter a video prompt/topic."}, status=400)

    scene_count = int(body.get("scene_count") or 64)
    auto_produce = bool(body.get("auto_produce", False))
    settings = body.get("settings") or {}

    pid = f"proj_{uuid.uuid4().hex[:8]}"
    project = {
        "id": pid,
        "title": prompt[:72],
        "logline": f"Architecting {scene_count}-beat long-form storyboard...",
        "topic": prompt,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "settings": {
            "style_id": settings.get("style_id", "galactic_highway"),
            "image_model": settings.get("image_model", "bytedance-seed/seedream-5-0-flash"),
            "tts_model": settings.get("tts_model", "microsoft/mai-voice-2.1"),
            "tts_voice": settings.get("tts_voice", "en-US-Grant:MAI-Voice-2.1"),
            "llm_model": settings.get("llm_model", "anthropic/claude-sonnet-5.5"),
            "visual_density": settings.get("visual_density", "smart_2x"),
            "aspect_ratio": settings.get("aspect_ratio", "16:9"),
            "caption_style": settings.get("caption_style", "none"),
            "include_sfx": settings.get("include_sfx", True),
            "include_ambient": settings.get("include_ambient", True),
            "include_chapter_cards": settings.get("include_chapter_cards", False),
        },
        "chapters": [],
        "scenes": [],
        "video_file": None,
        "srt_file": None,
        "total_duration": 0.0,
    }
    _save_project(project)

    if auto_produce:
        ACTIVE_JOBS[pid] = {
            "status": "running",
            "stage": "scripting",
            "detail": f"Architecting {scene_count}-beat long-form script across chapters...",
            "completed": 1,
            "total": scene_count + 10,
            "percent": 2,
        }
        asyncio.create_task(
            _run_full_production_job(
                pid,
                force_regenerate=False,
                generate_script_first=True,
                script_topic=prompt,
                script_scene_count=scene_count,
            )
        )
        return web.json_response({"project": _decorate_project_urls(project)})

    async def _script_only_job():
        try:
            await _populate_project_script(project, topic=prompt, scene_count=scene_count)
            ACTIVE_JOBS[pid] = {
                "status": "completed",
                "stage": "script_ready",
                "detail": f"Storyboard ready ({len(project['scenes'])} beats across {len(project['chapters'])} chapters)!",
                "completed": 10,
                "total": 10,
                "percent": 100,
            }
        except Exception as e:
            ACTIVE_JOBS[pid] = {
                "status": "error",
                "stage": "failed",
                "detail": str(e),
                "completed": 0,
                "total": 1,
                "percent": 0,
            }

    ACTIVE_JOBS[pid] = {
        "status": "running",
        "stage": "scripting",
        "detail": f"Planning {scene_count}-beat multi-chapter outline...",
        "completed": 1,
        "total": 10,
        "percent": 8,
    }
    asyncio.create_task(_script_only_job())
    return web.json_response({"project": _decorate_project_urls(project)})


async def handle_generate_all(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    _load_project(pid)
    body = await request.json() if request.can_read_body else {}
    force = bool(body.get("force", False))

    cur = ACTIVE_JOBS.get(pid)
    if cur and cur.get("status") == "running":
        return web.json_response({"job": cur})

    ACTIVE_JOBS[pid] = {
        "status": "running",
        "stage": "queued",
        "detail": "Starting long-form production pipeline...",
        "completed": 0,
        "total": 10,
        "percent": 2,
    }
    asyncio.create_task(_run_full_production_job(pid, force_regenerate=force))
    return web.json_response({"job": ACTIVE_JOBS[pid]})


async def handle_cancel_job(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    CANCEL_FLAGS.add(pid)
    if pid in ACTIVE_JOBS and ACTIVE_JOBS[pid].get("status") == "running":
        ACTIVE_JOBS[pid]["detail"] = "Pausing after active requests finish..."
    return web.json_response({"cancelled": True})


async def handle_render_project(request: web.Request) -> web.Response:
    pid = request.match_info["id"]
    project = _load_project(pid)
    pdir = _project_path(pid)
    body = await request.json() if request.can_read_body else {}
    if "settings" in body and isinstance(body["settings"], dict):
        project["settings"].update(body["settings"])
        _save_project(project)

    ready_only = bool(body.get("ready_scenes_only", True))
    render_res = await render_project_video(project, pdir, ready_scenes_only=ready_only)
    project["video_file"] = render_res["video_file"]
    project["srt_file"] = render_res["srt_file"]
    project["chapters_file"] = render_res["chapters_file"]
    project["chapters_text"] = render_res["chapters_text"]
    project["total_duration"] = render_res["total_duration"]
    _save_project(project)
    return web.json_response({"project": _decorate_project_urls(project), "render": render_res})


async def handle_tts_preview(request: web.Request) -> web.Response:
    body = await request.json()
    tts_model = body.get("tts_model", "microsoft/mai-voice-2.1")
    voice = body.get("tts_voice", "en-US-Grant:MAI-Voice-2.1")
    text = (
        body.get("text")
        or "The sirens start at 6:14 a.m. Not the monthly test... you know the difference. You grab your bag, and you run."
    )

    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{tts_model}_{voice}")
    out_path = SFX_DIR / f"preview_{safe_slug}.mp3"
    info = await generate_scene_speech(
        text=text,
        output_path=out_path,
        tts_model=tts_model,
        voice=voice,
    )
    return web.json_response(
        {
            "audio_url": f"/media/projects/_sfx_cache/{out_path.name}?t={int(time.time())}",
            "info": info,
        }
    )


async def handle_sfx_preview(request: web.Request) -> web.Response:
    cue = request.match_info["cue"]
    path = await asyncio.to_thread(ensure_sfx_file, cue)
    if not path or not path.exists():
        return web.json_response({"error": "Invalid SFX cue"}, status=404)
    return web.json_response({"audio_url": f"/media/projects/_sfx_cache/{path.name}"})


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware], client_max_size=50 * 1024 * 1024)

    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/settings/key", handle_update_key)
    app.router.add_post("/api/cast/generate", handle_create_or_generate_cast_member)
    app.router.add_get("/api/reference", handle_reference_info)
    app.router.add_post("/api/reference/download", handle_download_youtube_ref)

    app.router.add_get("/api/projects", handle_list_projects)
    app.router.add_post("/api/projects", handle_create_project)
    app.router.add_post("/api/projects/create-from-prompt", handle_create_from_prompt)
    app.router.add_get("/api/projects/{id}", handle_get_project)
    app.router.add_put("/api/projects/{id}", handle_update_project)
    app.router.add_delete("/api/projects/{id}", handle_delete_project)

    app.router.add_post("/api/projects/{id}/generate-script", handle_generate_script)
    app.router.add_post("/api/projects/{id}/scenes/{scene_id}/generate-image", handle_generate_scene_image)
    app.router.add_post("/api/projects/{id}/scenes/{scene_id}/generate-audio", handle_generate_scene_audio)
    app.router.add_post("/api/projects/{id}/generate-all", handle_generate_all)
    app.router.add_post("/api/projects/{id}/cancel-job", handle_cancel_job)
    app.router.add_post("/api/projects/{id}/render", handle_render_project)

    app.router.add_post("/api/tts/preview", handle_tts_preview)
    app.router.add_get("/api/sfx/preview/{cue}", handle_sfx_preview)

    app.router.add_static("/media/projects", str(PROJECTS_DIR), show_index=False)
    app.router.add_static("/media/reference", str(REFERENCE_DIR), show_index=False)

    dist_dir = BASE_DIR / "web" / "dist"
    if dist_dir.exists():
        app.router.add_static("/assets", str(dist_dir / "assets"), show_index=False)

        async def serve_spa(request: web.Request):
            return web.FileResponse(dist_dir / "index.html")

        app.router.add_get("/", serve_spa)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8788"))
    web.run_app(create_app(), host="0.0.0.0", port=port)
