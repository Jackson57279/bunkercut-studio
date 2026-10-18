import wave
from pathlib import Path
import numpy as np
from .config import SFX_DIR

SAMPLE_RATE = 24000


def _save_wav(path: Path, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Path:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return path


def ensure_sfx_file(cue: str) -> Path | None:
    if not cue or cue == "none":
        return None
    out_path = SFX_DIR / f"sfx_{cue}.wav"
    if out_path.exists() and out_path.stat().st_size > 1000:
        return out_path

    rng = np.random.default_rng(42)

    if cue == "siren":
        dur = 4.0
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        freq = 420.0 + 340.0 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.35 * t - np.pi / 2))
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        tone = 0.55 * np.sin(phase) + 0.25 * np.sin(phase * 1.498) + 0.12 * np.sin(phase * 2.0)
        env = np.minimum(t / 0.4, 1.0) * np.minimum((dur - t) / 0.6, 1.0)
        samples = np.tanh(tone * 1.4) * env * 0.35
        return _save_wav(out_path, samples)

    if cue == "radio_static":
        dur = 2.8
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        noise = rng.normal(0, 1, len(t))
        crackle = np.convolve(noise, np.ones(8) / 8.0, mode="same")
        whistle = 0.22 * np.sin(2 * np.pi * (1400 + 600 * np.sin(2 * np.pi * 1.7 * t)) * t)
        gate = (np.sin(2 * np.pi * 6.5 * t) > -0.3).astype(float)
        env = np.minimum(t / 0.15, 1.0) * np.minimum((dur - t) / 0.4, 1.0)
        samples = (crackle * 0.45 * gate + whistle * 0.3) * env * 0.32
        return _save_wav(out_path, samples)

    if cue == "hatch_seal":
        dur = 2.2
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        slam_t = np.maximum(0.0, t - 0.1)
        slam = (
            np.sin(2 * np.pi * 68 * slam_t) * np.exp(-slam_t * 9.0)
            + 0.6 * np.sin(2 * np.pi * 142 * slam_t) * np.exp(-slam_t * 16.0)
            + 0.4 * rng.normal(0, 1, len(t)) * np.exp(-slam_t * 28.0)
        ) * (t >= 0.1)
        lock_t = np.maximum(0.0, t - 0.9)
        lock = (
            0.45 * np.sin(2 * np.pi * 520 * lock_t) * np.exp(-lock_t * 14.0)
            + 0.35 * np.sin(2 * np.pi * 290 * lock_t) * np.exp(-lock_t * 10.0)
        ) * (t >= 0.9)
        samples = np.tanh((slam + lock) * 1.5) * 0.45
        return _save_wav(out_path, samples)

    if cue == "geiger":
        dur = 3.5
        n = int(SAMPLE_RATE * dur)
        samples = np.zeros(n)
        click_positions = rng.choice(n - 120, size=55, replace=False)
        for pos in click_positions:
            click_len = 80
            t_c = np.linspace(0, click_len / SAMPLE_RATE, click_len)
            burst = (
                np.sin(2 * np.pi * 2400 * t_c) * np.exp(-t_c * 900)
                + 0.5 * rng.normal(0, 1, click_len) * np.exp(-t_c * 1200)
            )
            samples[pos : pos + click_len] += burst * 0.55
        return _save_wav(out_path, samples)

    if cue == "power_down":
        dur = 3.2
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        freq = 320.0 * np.exp(-t * 0.85) + 28.0
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        turbine = 0.5 * np.sin(phase) + 0.3 * np.sin(phase * 2.0)
        relay_click = 0.6 * rng.normal(0, 1, len(t)) * np.exp(-np.abs(t - 0.08) * 90.0)
        env = np.exp(-t * 0.65)
        samples = (turbine * env + relay_click) * 0.38
        return _save_wav(out_path, samples)

    if cue == "heartbeat":
        dur = 3.6
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        samples = np.zeros_like(t)
        for beat_start in [0.2, 1.25, 2.3]:
            for offset, amp in [(0.0, 0.8), (0.24, 0.55)]:
                bt = np.maximum(0.0, t - (beat_start + offset))
                mask = (t >= (beat_start + offset)).astype(float)
                thump = amp * np.sin(2 * np.pi * 52 * bt) * np.exp(-bt * 18.0) * mask
                samples += thump
        return _save_wav(out_path, samples * 0.5)

    if cue == "explosion_rumble":
        dur = 4.0
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        noise = rng.normal(0, 1, len(t))
        kernel = np.exp(-np.linspace(0, 4, 160))
        kernel /= kernel.sum()
        low_rumble = np.convolve(noise, kernel, mode="same") * 3.5
        sub = 0.6 * np.sin(2 * np.pi * 38 * t) * np.exp(-t * 0.7)
        env = np.minimum(t / 0.08, 1.0) * np.exp(-t * 0.55)
        samples = np.tanh((low_rumble + sub) * env * 1.4) * 0.45
        return _save_wav(out_path, samples)

    if cue == "bunker_hum":
        dur = 4.0
        t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
        hum = (
            0.4 * np.sin(2 * np.pi * 60 * t)
            + 0.25 * np.sin(2 * np.pi * 120 * t)
            + 0.1 * np.sin(2 * np.pi * 180 * t)
            + 0.08 * rng.normal(0, 1, len(t))
        )
        env = np.minimum(t / 0.3, 1.0) * np.minimum((dur - t) / 0.3, 1.0)
        return _save_wav(out_path, hum * env * 0.22)

    return None


def ensure_ambient_drone_loop() -> Path:
    """Generates a seamless 20-second loopable atmospheric audio bed for long-form videos of any length."""
    out_path = SFX_DIR / "ambient_drone_loop_20s.wav"
    if out_path.exists() and out_path.stat().st_size > 1000:
        return out_path

    dur = 20.0
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    # Frequencies chosen as exact integer multiples of 1/20Hz (0.05Hz) so the 20s boundary is phase-continuous
    lfo1 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.10 * t)
    lfo2 = 0.5 + 0.5 * np.cos(2 * np.pi * 0.05 * t)
    drone = (
        0.38 * np.sin(2 * np.pi * 36.70 * t)
        + 0.28 * np.sin(2 * np.pi * 55.00 * t) * lfo1
        + 0.22 * np.sin(2 * np.pi * 73.40 * t + 0.35 * np.sin(2 * np.pi * 0.10 * t))
        + 0.12 * np.sin(2 * np.pi * 87.30 * t) * lfo2
    )
    samples = drone * 0.18
    return _save_wav(out_path, samples)
