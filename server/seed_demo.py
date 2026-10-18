import asyncio
import json
import time
from .app import _project_path, _run_full_production_job, _save_project

DEMO_PROJECT_ID = "proj_bunker_demo"


async def ensure_demo_project() -> None:
    pdir = _project_path(DEMO_PROJECT_ID)
    if (pdir / "final_video.mp4").exists():
        print("Demo project already rendered at:", pdir / "final_video.mp4")
        return

    project = {
        "id": DEMO_PROJECT_ID,
        "title": "Bunker Survival: Protocol Zero (Day 1 to Day 90)",
        "logline": "When the 6:14 AM civil defense sirens don't stop, you have 8 minutes to seal the hatch and survive on closed-loop rations.",
        "topic": "Surviving the first 90 days in a backyard fallout bunker: the 6:14 AM siren, sealing the steel hatch, rationing MREs and 2,000 gallons of water, potassium iodide protocol, and the mysterious sensor spike on Day 71.",
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "settings": {
            "style_id": "galactic_highway",
            "image_model": "bytedance-seed/seedream-5-0-flash",
            "tts_model": "fish-audio/s2.1-pro",
            "tts_voice": "clone_reference",
            "llm_model": "google/gemini-2.5-flash",
            "aspect_ratio": "16:9",
            "caption_style": "documentary",
            "include_sfx": True,
            "include_ambient": True,
            "character_anchor_id": "bed_siren",
        },
        "chapters": [
            {"title": "The 6:14 AM Siren", "start_scene_index": 0},
            {"title": "Sealing the Shelter", "start_scene_index": 2},
            {"title": "Stocking & Rations", "start_scene_index": 3},
            {"title": "Day 71 Anomaly", "start_scene_index": 5},
        ],
        "scenes": [
            {
                "id": "scene_01",
                "scene_number": 1,
                "chapter": "The 6:14 AM Siren",
                "title": "The 6:14 AM Wake-Up",
                "narration": "The sirens start at 6:14 a.m. Not the monthly test. You know the difference because these don't stop.",
                "visual_prompt": "The 2D stick-figure man with thin black stick limbs, white round head, brown hair, and bright orange baseball cap sitting bolt upright in bed looking startled at a green digital alarm clock reading '6:14' on a wooden nightstand, while outside the window a grey siren tower emits red sound wave arcs.",
                "label_overlay": "6:14 AM",
                "use_character_ref": True,
                "camera_motion": "zoom_in",
                "sfx_cue": "siren",
            },
            {
                "id": "scene_02",
                "scene_number": 2,
                "chapter": "The 6:14 AM Siren",
                "title": "Eight Minutes Left",
                "narration": "Your phone buzzes with an emergency alert, then goes dead. You have maybe eight minutes before fallout reaches the valley.",
                "visual_prompt": "The 2D stick-figure man with the bright orange baseball cap standing against a stark pure white background holding a smartphone displaying a red warning triangle icon, while giant bold black sans-serif text on the right reads '8:00'.",
                "label_overlay": "8:00",
                "use_character_ref": True,
                "camera_motion": "shake",
                "sfx_cue": "radio_static",
            },
            {
                "id": "scene_03",
                "scene_number": 3,
                "chapter": "Sealing the Shelter",
                "title": "Sprint to the Hatch",
                "narration": "You grab your go-bag, sprint across the grass, and haul the heavy steel bunker hatch open before spinning the locking wheel shut.",
                "visual_prompt": "The 2D stick-figure man wearing the bright orange baseball cap and an olive-green backpack running fast with horizontal speed lines across a flat green lawn toward an open round grey steel underground bunker hatch with a metal ladder leading down.",
                "label_overlay": "",
                "use_character_ref": True,
                "camera_motion": "pan_right",
                "sfx_cue": "hatch_seal",
            },
            {
                "id": "scene_04",
                "scene_number": 4,
                "chapter": "Stocking & Rations",
                "title": "Five Years of Rations",
                "narration": "Down here, preparation is measured in calories. Fifteen hundred pounds of grain, two thousand gallons of water, and stacked cases of MREs for emergencies.",
                "visual_prompt": "Inside a clean white-paneled underground bunker room, the 2D stick-figure man in the bright orange baseball cap inspects a brown pouch labeled 'MRE' next to neatly stacked tan cardboard boxes each labeled 'MRE' in bold black letters.",
                "label_overlay": "MRE",
                "use_character_ref": True,
                "camera_motion": "zoom_out",
                "sfx_cue": "bunker_hum",
            },
            {
                "id": "scene_05",
                "scene_number": 5,
                "chapter": "Stocking & Rations",
                "title": "Medical & Thyroid Protocol",
                "narration": "On a steel tray sit dental tools, antibiotics, and potassium iodide tablets to shield your thyroid during the first forty-eight hours.",
                "visual_prompt": "Clean isolated 2D flat vector explainer illustration on a stark pure white background showing a grey stainless steel medical tray with four silver dental instruments on the left, and a white-and-blue medicine box labeled 'POTASSIUM IODIDE' with three white round tablets on the right.",
                "label_overlay": "POTASSIUM IODIDE",
                "use_character_ref": False,
                "camera_motion": "zoom_in",
                "sfx_cue": "geiger",
            },
            {
                "id": "scene_06",
                "scene_number": 6,
                "chapter": "Day 71 Anomaly",
                "title": "Unidentified Surface Reading",
                "narration": "By Day 71, the radiation gauge finally drops into the green. Pair by pair, though, the air sensor detects an unidentified particle still rising outside.",
                "visual_prompt": "Inside the white bunker room with a bunk bed and steel ladder to the ceiling hatch on the left, the 2D stick-figure man in the bright orange baseball cap sits at a grey desk staring at a monitor displaying a radiation gauge needle in the red zone and a storage shelf of blue water jugs and first-aid kit on the right.",
                "label_overlay": "DAY 71",
                "use_character_ref": True,
                "camera_motion": "zoom_in",
                "sfx_cue": "heartbeat",
            },
        ],
        "video_file": None,
        "srt_file": None,
        "total_duration": 0.0,
    }

    _save_project(project)
    print("Running full production job for demo project...")
    await _run_full_production_job(DEMO_PROJECT_ID, force_regenerate=False)
    final_proj = json.loads((pdir / "project.json").read_text())
    print("Demo project complete! Video:", final_proj.get("video_file"), "Duration:", final_proj.get("total_duration"))


if __name__ == "__main__":
    asyncio.run(ensure_demo_project())
