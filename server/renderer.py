import asyncio
import hashlib
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Callable, Optional
from PIL import Image, ImageDraw, ImageFont

from .openrouter import probe_audio_duration
from .sfx import ensure_ambient_drone_loop, ensure_sfx_file


def _format_srt_time(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        seconds += 1
        ms = 0
    total_s = int(seconds)
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_ass_time(seconds: float) -> str:
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        seconds += 1
        cs = 0
    total_s = int(seconds)
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _format_yt_chapter_time(seconds: float) -> str:
    total_s = int(round(seconds))
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _render_chapter_card_clip_sync(
    chapter_idx: int,
    chapter_title: str,
    project_dir: Path,
    aspect_ratio: str = "16:9",
) -> Path:
    """
    Renders a crisp, zero-API-cost 2.0-second Chapter Title Card clip (e.g. CHAPTER 02 // WATER & POWER)
    to elevate 20-minute video pacing and structure.
    """
    cards_dir = project_dir / "scenes"
    cards_dir.mkdir(parents=True, exist_ok=True)
    safe_slug = hashlib.sha1(f"{chapter_idx}:{chapter_title}:{aspect_ratio}".encode()).hexdigest()[:10]
    clip_path = cards_dir / f"chapter_card_{chapter_idx:02d}_{safe_slug}.mp4"
    if clip_path.exists() and clip_path.stat().st_size > 1000:
        return clip_path

    w, h = (1920, 1080) if aspect_ratio != "9:16" else (1080, 1920)
    im = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(im)

    # Minimalist black frame border + chapter number & title
    pad = 80
    draw.rectangle([pad, pad, w - pad, h - pad], outline=(18, 18, 18), width=4)
    draw.line([pad + 60, h // 2 - 20, w - pad - 60, h // 2 - 20], fill=(220, 220, 220), width=2)

    try:
        font_sm = ImageFont.truetype("/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono-Bold.ttf", 34)
        font_lg = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 68)
    except Exception:
        font_sm = ImageFont.load_default()
        font_lg = ImageFont.load_default()

    eyebrow = f"PART {chapter_idx:02d}"
    title_up = chapter_title.upper()

    eb_box = draw.textbbox((0, 0), eyebrow, font=font_sm)
    eb_w = eb_box[2] - eb_box[0]
    draw.rectangle(
        [w // 2 - eb_w // 2 - 24, h // 2 - 115, w // 2 + eb_w // 2 + 24, h // 2 - 55],
        fill=(18, 18, 18),
    )
    draw.text((w // 2 - eb_w // 2, h // 2 - 104), eyebrow, fill=(255, 255, 255), font=font_sm)

    t_box = draw.textbbox((0, 0), title_up, font=font_lg)
    t_w = t_box[2] - t_box[0]
    draw.text((max(pad + 40, w // 2 - t_w // 2), h // 2 + 12), title_up, fill=(18, 18, 18), font=font_lg)

    png_path = cards_dir / f"chapter_card_{chapter_idx:02d}_{safe_slug}.png"
    im.save(png_path, format="PNG")

    sfx_path = ensure_sfx_file("hatch_seal")
    dur = 1.9
    cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(png_path)]
    if sfx_path and sfx_path.exists():
        cmd += [
            "-i",
            str(sfx_path),
            "-filter_complex",
            f"[0:v]scale={w}:{h},format=yuv420p[v];[1:a]aresample=44100,volume=0.22,afade=t=out:st=1.2:d=0.6[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
        ]
    else:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex",
            f"[0:v]scale={w}:{h},format=yuv420p[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
        ]

    cmd += [
        "-t",
        str(dur),
        "-c:v",
        "libopenh264",
        "-b:v",
        "4500k",
        "-maxrate",
        "6000k",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(clip_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return clip_path


def _build_scene_ass_subtitles(
    narration: str,
    duration: float,
    ass_path: Path,
    caption_style: str,
    aspect_ratio: str = "16:9",
) -> Path:
    play_res_x, play_res_y = (1920, 1080) if aspect_ratio != "9:16" else (1080, 1920)
    words = narration.strip().split()
    if not words:
        words = ["..."]

    if caption_style == "kinetic":
        font_size = 64 if aspect_ratio == "16:9" else 74
        margin_v = 110 if aspect_ratio == "16:9" else 280
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{font_size},&H0000D4FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,1,4,2,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        chunks = [" ".join(words[i : i + 4]) for i in range(0, len(words), 4)]
        total_chars = max(1, sum(len(c) for c in chunks))
        t_cur = 0.05
        usable_dur = max(0.5, duration - 0.15)
        events = []
        for chunk in chunks:
            seg_dur = usable_dur * (len(chunk) / total_chars)
            t_end = min(duration - 0.05, t_cur + seg_dur)
            safe_txt = chunk.upper().replace("{", "").replace("}", "")
            events.append(
                f"Dialogue: 0,{_format_ass_time(t_cur)},{_format_ass_time(t_end)},Default,,0,0,0,,{safe_txt}"
            )
            t_cur = t_end
        ass_path.write_text(header + "\n".join(events))
        return ass_path

    font_size = 44 if aspect_ratio == "16:9" else 52
    margin_v = 64 if aspect_ratio == "16:9" else 200
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,&H000000FF,&H66000000,&HAA000000,-1,0,0,0,100,100,0,0,3,14,0,2,90,90,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chunks = [" ".join(words[i : i + 10]) for i in range(0, len(words), 10)]
    total_chars = max(1, sum(len(c) for c in chunks))
    t_cur = 0.05
    usable_dur = max(0.5, duration - 0.15)
    events = []
    for chunk in chunks:
        seg_dur = usable_dur * (len(chunk) / total_chars)
        t_end = min(duration - 0.05, t_cur + seg_dur)
        wrapped = "\\N".join(textwrap.wrap(chunk.replace("{", "").replace("}", ""), width=46))
        events.append(
            f"Dialogue: 0,{_format_ass_time(t_cur)},{_format_ass_time(t_end)},Default,,0,0,0,,{wrapped}"
        )
        t_cur = t_end
    ass_path.write_text(header + "\n".join(events))
    return ass_path


def _compute_scene_render_sig(
    img_path: Path,
    aud_path: Path,
    narration: str,
    motion: str,
    shot_variant: str,
    caption_style: str,
    sfx_cue: str,
    aspect_ratio: str,
) -> str:
    raw = (
        f"{img_path.stat().st_mtime_ns}:{aud_path.stat().st_mtime_ns}:"
        f"{narration}:{motion}:{shot_variant}:{caption_style}:{sfx_cue}:{aspect_ratio}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _render_single_scene_sync(
    scene: dict[str, Any],
    project_dir: Path,
    aspect_ratio: str = "16:9",
    caption_style: str = "none",
    include_sfx: bool = True,
    scene_padding: float = 0.30,
) -> dict[str, Any]:
    scene_id = scene["id"]
    img_path = project_dir / (scene.get("image_file") or f"scenes/{scene_id}.png")
    aud_path = project_dir / (scene.get("audio_file") or f"scenes/{scene_id}.mp3")
    clip_rel = f"scenes/{scene_id}_clip.mp4"
    clip_path = project_dir / clip_rel

    if not img_path.exists():
        raise RuntimeError(f"Scene {scene.get('scene_number')} is missing its generated image.")
    if not aud_path.exists():
        raise RuntimeError(f"Scene {scene.get('scene_number')} is missing its voiceover audio.")

    motion = scene.get("camera_motion", "zoom_in")
    shot_variant = scene.get("shot_variant", "wide")
    sfx_cue = scene.get("sfx_cue", "none") if include_sfx else "none"
    sig = _compute_scene_render_sig(
        img_path,
        aud_path,
        scene.get("narration", ""),
        motion,
        shot_variant,
        caption_style,
        sfx_cue,
        aspect_ratio,
    )

    voice_dur = probe_audio_duration(aud_path)
    total_dur = round(voice_dur + scene_padding, 2)

    if scene.get("render_sig") == sig and clip_path.exists() and clip_path.stat().st_size > 1000:
        return {
            "clip_file": clip_rel,
            "duration": total_dur,
            "render_sig": sig,
            "cached": True,
        }

    fps = 30
    total_frames = max(30, int(round(total_dur * fps)))
    w, h = (1920, 1080) if aspect_ratio != "9:16" else (1080, 1920)
    upscale_w, upscale_h = int(w * 1.28), int(h * 1.28)

    # Smart Multi-Angle / Editorial Punch-In Jump-Cut when reusing a master illustration across 2 or 3 beats
    if shot_variant == "punch_in":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='1.18':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif shot_variant == "focus_left":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='1.18':x='iw*0.14':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif shot_variant == "focus_right":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='1.18':x='iw-iw/zoom-iw*0.14':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif motion == "zoom_in":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='min(zoom+0.00025,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif motion == "zoom_out":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='if(eq(on,1),1.12,max(1.0,zoom-0.00045))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif motion == "pan_right":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='1.10':x='(iw-iw/zoom)*(on/{total_frames})':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif motion == "pan_left":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='1.10':x='(iw-iw/zoom)*(1-on/{total_frames})':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    elif motion == "shake":
        zp = (
            f"scale={upscale_w}:{upscale_h},"
            f"zoompan=z='1.08':x='iw/2-(iw/zoom/2)+sin(on*1.7)*10':y='ih/2-(ih/zoom/2)+cos(on*2.3)*8':"
            f"d={total_frames}:s={w}x{h}:fps={fps}"
        )
    else:
        zp = f"scale={w}:{h},fps={fps}"

    vf_parts = [zp]
    if caption_style in ("documentary", "kinetic"):
        ass_path = project_dir / "scenes" / f"{scene_id}.ass"
        _build_scene_ass_subtitles(
            scene.get("narration", ""),
            total_dur,
            ass_path,
            caption_style=caption_style,
            aspect_ratio=aspect_ratio,
        )
        escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf_parts.append(f"ass='{escaped_ass}'")

    vf_parts.append("format=yuv420p")
    vf_chain = ",".join(vf_parts)

    sfx_path = ensure_sfx_file(sfx_cue)

    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(img_path), "-i", str(aud_path)]
    if sfx_path and sfx_path.exists():
        cmd += [
            "-i",
            str(sfx_path),
            "-filter_complex",
            (
                f"[0:v]{vf_chain}[v];"
                f"[1:a]aresample=44100,apad=pad_dur={scene_padding}[vo];"
                f"[2:a]aresample=44100,volume=0.26,apad=pad_dur={total_dur}[sfx];"
                f"[vo][sfx]amix=inputs=2:duration=first:dropout_transition=1[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
        ]
    else:
        cmd += [
            "-filter_complex",
            f"[0:v]{vf_chain}[v];[1:a]aresample=44100,apad=pad_dur={scene_padding}[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
        ]

    cmd += [
        "-t",
        str(total_dur),
        "-c:v",
        "libopenh264",
        "-b:v",
        "4500k",
        "-maxrate",
        "6000k",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(clip_path),
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return {
        "clip_file": clip_rel,
        "duration": total_dur,
        "render_sig": sig,
        "cached": False,
    }


async def render_project_video(
    project: dict[str, Any],
    project_dir: Path,
    ready_scenes_only: bool = False,
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> dict[str, Any]:
    all_scenes = project.get("scenes", [])
    if ready_scenes_only:
        scenes = [
            sc
            for sc in all_scenes
            if (project_dir / (sc.get("image_file") or f"scenes/{sc['id']}.png")).exists()
            and (project_dir / (sc.get("audio_file") or f"scenes/{sc['id']}.mp3")).exists()
        ]
    else:
        scenes = all_scenes

    if not scenes:
        raise RuntimeError("No scenes with both image and audio are ready to render.")

    settings = project.get("settings", {})
    aspect_ratio = settings.get("aspect_ratio", "16:9")
    caption_style = settings.get("caption_style", "documentary")
    include_sfx = bool(settings.get("include_sfx", True))
    include_ambient = bool(settings.get("include_ambient", True))
    include_chapter_cards = bool(settings.get("include_chapter_cards", True))

    sem = asyncio.Semaphore(6)
    done_cnt = 0

    async def _render_one(sc: dict[str, Any]) -> None:
        nonlocal done_cnt
        async with sem:
            res = await asyncio.to_thread(
                _render_single_scene_sync,
                sc,
                project_dir,
                aspect_ratio,
                caption_style,
                include_sfx,
            )
            sc["clip_file"] = res["clip_file"]
            sc["duration"] = res["duration"]
            sc["render_sig"] = res["render_sig"]
            done_cnt += 1
            if progress_cb:
                progress_cb(
                    f"Rendered scene clip {done_cnt}/{len(scenes)} ({'cached' if res.get('cached') else 'encoded'})",
                    done_cnt,
                    len(scenes),
                )

    await asyncio.gather(*[_render_one(sc) for sc in scenes])

    concat_file = project_dir / "concat_list.txt"
    concat_lines = []
    srt_blocks = []
    chapter_lines = []
    seen_chapters = set()
    elapsed = 0.0
    srt_index = 1

    for sc in scenes:
        ch_title = (sc.get("chapter") or "").strip()
        if ch_title and ch_title not in seen_chapters:
            seen_chapters.add(ch_title)
            chapter_lines.append(f"{_format_yt_chapter_time(elapsed)} {ch_title}")
            if include_chapter_cards and len(seen_chapters) >= 1:
                ch_card_clip = await asyncio.to_thread(
                    _render_chapter_card_clip_sync,
                    len(seen_chapters),
                    ch_title,
                    project_dir,
                    aspect_ratio,
                )
                concat_lines.append(f"file '{ch_card_clip.resolve()}'")
                elapsed += 1.9

        clip_abs = (project_dir / sc["clip_file"]).resolve()
        concat_lines.append(f"file '{clip_abs}'")
        dur = float(sc.get("duration", 5.5))
        start_t = elapsed
        end_t = elapsed + dur

        narration = (sc.get("narration") or "").strip()
        if narration:
            srt_blocks.append(
                f"{srt_index}\n{_format_srt_time(start_t)} --> {_format_srt_time(end_t)}\n{narration}\n"
            )
            srt_index += 1
        elapsed = end_t

    concat_file.write_text("\n".join(concat_lines) + "\n")
    srt_path = project_dir / "subtitles.srt"
    srt_path.write_text("\n".join(srt_blocks))

    chapters_path = project_dir / "youtube_chapters.txt"
    chapters_path.write_text("\n".join(chapter_lines))

    raw_concat_mp4 = project_dir / "concat_raw.mp4"
    final_mp4 = project_dir / "final_video.mp4"

    await asyncio.to_thread(
        subprocess.run,
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(raw_concat_mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if include_ambient:
        drone_loop_wav = await asyncio.to_thread(ensure_ambient_drone_loop)
        await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_concat_mp4),
                "-stream_loop",
                "-1",
                "-i",
                str(drone_loop_wav),
                "-filter_complex",
                "[0:a]volume=1.0[vo];[1:a]aresample=44100,volume=0.14[bg];[vo][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map",
                "0:v",
                "-map",
                "[a]",
                "-t",
                str(round(elapsed, 2)),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(final_mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        raw_concat_mp4.unlink(missing_ok=True)
    else:
        raw_concat_mp4.replace(final_mp4)

    return {
        "video_file": "final_video.mp4",
        "srt_file": "subtitles.srt",
        "chapters_file": "youtube_chapters.txt",
        "total_duration": round(elapsed, 2),
        "rendered_scenes": len(scenes),
        "chapters_text": "\n".join(chapter_lines),
    }
