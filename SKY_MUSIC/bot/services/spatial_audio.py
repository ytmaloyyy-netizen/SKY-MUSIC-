from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
import librosa
import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class SpatialModeConfig:
    tier: str          # "8D", "16D", "32D"
    mode_key: str
    mode_title: str
    base_rate_hz: float
    harmonic_mult: float
    depth_ms: float
    reverb_mix: float
    atmosphere_mix: float

    def to_json(self, intensity: float) -> str:
        return json.dumps(
            {
                "tier": self.tier,
                "mode": self.mode_title,
                "intensity": intensity,
                "rate_hz": self.base_rate_hz,
                "harmonic_mult": self.harmonic_mult,
                "depth_ms": self.depth_ms,
                "reverb_mix": self.reverb_mix,
                "atmosphere_mix": self.atmosphere_mix,
            },
            ensure_ascii=False,
        )


SPATIAL_MODES: dict[str, SpatialModeConfig] = {
    # 8D AUDIO
    "8d_classic_orbit": SpatialModeConfig(
        tier="8D", mode_key="8d_classic_orbit", mode_title="Classic Orbit",
        base_rate_hz=0.14, harmonic_mult=1.0, depth_ms=6.0, reverb_mix=0.22, atmosphere_mix=0.10,
    ),
    "8d_smooth_rotation": SpatialModeConfig(
        tier="8D", mode_key="8d_smooth_rotation", mode_title="Smooth Rotation",
        base_rate_hz=0.22, harmonic_mult=1.0, depth_ms=8.0, reverb_mix=0.25, atmosphere_mix=0.12,
    ),
    "8d_deep_space": SpatialModeConfig(
        tier="8D", mode_key="8d_deep_space", mode_title="Deep Space",
        base_rate_hz=0.09, harmonic_mult=1.5, depth_ms=11.0, reverb_mix=0.42, atmosphere_mix=0.24,
    ),
    "8d_atmospheric": SpatialModeConfig(
        tier="8D", mode_key="8d_atmospheric", mode_title="Atmospheric",
        base_rate_hz=0.12, harmonic_mult=1.25, depth_ms=9.0, reverb_mix=0.35, atmosphere_mix=0.20,
    ),
    # 16D AUDIO
    "16d_double_orbit": SpatialModeConfig(
        tier="16D", mode_key="16d_double_orbit", mode_title="Double Orbit",
        base_rate_hz=0.18, harmonic_mult=2.0, depth_ms=12.0, reverb_mix=0.32, atmosphere_mix=0.22,
    ),
    "16d_hyper_rotation": SpatialModeConfig(
        tier="16D", mode_key="16d_hyper_rotation", mode_title="Hyper Rotation",
        base_rate_hz=0.34, harmonic_mult=2.0, depth_ms=13.5, reverb_mix=0.28, atmosphere_mix=0.18,
    ),
    "16d_deep_atmosphere": SpatialModeConfig(
        tier="16D", mode_key="16d_deep_atmosphere", mode_title="Deep Atmosphere",
        base_rate_hz=0.10, harmonic_mult=2.5, depth_ms=15.0, reverb_mix=0.52, atmosphere_mix=0.34,
    ),
    "16d_surround_motion": SpatialModeConfig(
        tier="16D", mode_key="16d_surround_motion", mode_title="Surround Motion",
        base_rate_hz=0.24, harmonic_mult=1.75, depth_ms=14.0, reverb_mix=0.38, atmosphere_mix=0.26,
    ),
    # 32D AUDIO
    "32d_ultimate_space": SpatialModeConfig(
        tier="32D", mode_key="32d_ultimate_space", mode_title="Ultimate Space",
        base_rate_hz=0.16, harmonic_mult=3.0, depth_ms=17.0, reverb_mix=0.55, atmosphere_mix=0.40,
    ),
    "32d_infinity_orbit": SpatialModeConfig(
        tier="32D", mode_key="32d_infinity_orbit", mode_title="Infinity Orbit",
        base_rate_hz=0.20, harmonic_mult=2.5, depth_ms=18.0, reverb_mix=0.48, atmosphere_mix=0.35,
    ),
    "32d_hyper_atmosphere": SpatialModeConfig(
        tier="32D", mode_key="32d_hyper_atmosphere", mode_title="Hyper Atmosphere",
        base_rate_hz=0.11, harmonic_mult=3.5, depth_ms=19.0, reverb_mix=0.62, atmosphere_mix=0.45,
    ),
    "32d_advanced_motion": SpatialModeConfig(
        tier="32D", mode_key="32d_advanced_motion", mode_title="Advanced Motion",
        base_rate_hz=0.28, harmonic_mult=3.0, depth_ms=16.5, reverb_mix=0.44, atmosphere_mix=0.32,
    ),
}


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-y", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err_tail = (proc.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(f"Ошибка FFmpeg при пространственной обработке: {' | '.join(err_tail)}")


def _process_spatial_sync(
    input_path: Path,
    output_path: Path,
    mode: SpatialModeConfig,
    intensity: float,
) -> Path:
    work_dir = output_path.parent
    wav_in = work_dir / "spatial_in.wav"
    wav_panned = work_dir / "spatial_panned.wav"

    _run_ffmpeg(["-i", str(input_path), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(wav_in)])

    y, sr = librosa.load(str(wav_in), sr=44100, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y], axis=0)

    n_samples = y.shape[1]
    t = np.arange(n_samples, dtype=np.float32) / float(sr)
    k = max(0.05, min(1.5, float(intensity)))

    # Моно-основа для точного позиционирования и сохранения центрального образа
    mono = 0.5 * (y[0] + y[1])

    # Траектория панорамирования в диапазоне [-0.92 * k, +0.92 * k]
    primary_lfo = np.sin(2.0 * np.pi * mode.base_rate_hz * t)
    secondary_lfo = np.sin(2.0 * np.pi * (mode.base_rate_hz * mode.harmonic_mult) * t + np.pi / 4.0)
    pan = np.clip(0.75 * primary_lfo + 0.25 * secondary_lfo, -1.0, 1.0) * min(0.95, 0.85 * k)

    # Равномерное по мощности (constant-power) панорамирование
    angle = (pan + 1.0) * (np.pi / 4.0)
    gain_l = np.cos(angle)
    gain_r = np.sin(angle)

    # Плавная микрозадержка между каналами для ощущения глубины и пространства
    max_delay_samples = int((mode.depth_ms * k / 1000.0) * sr)
    delay_mod = ((primary_lfo + 1.0) * 0.5) * max_delay_samples
    idx_base = np.arange(n_samples, dtype=np.float32)

    right_delayed_idx = np.clip(idx_base - delay_mod, 0, n_samples - 1)
    left_delayed_idx = np.clip(idx_base - (max_delay_samples - delay_mod), 0, n_samples - 1)

    r_interp = np.interp(right_delayed_idx, idx_base, mono)
    l_interp = np.interp(left_delayed_idx, idx_base, mono)

    # Смешиваем исходное стерео и пространственный образ с учётом интенсивности
    wet_mix = min(0.95, 0.72 * k)
    out_l = (1.0 - wet_mix) * y[0] + wet_mix * (0.65 * mono * gain_l + 0.35 * l_interp * gain_l)
    out_r = (1.0 - wet_mix) * y[1] + wet_mix * (0.65 * mono * gain_r + 0.35 * r_interp * gain_r)

    stereo = np.stack([out_l, out_r], axis=0)
    sf.write(str(wav_panned), stereo.T, sr, subtype="PCM_16")

    # Добавляем реверберацию и атмосферный слой через FFmpeg
    rev_level = min(0.85, mode.reverb_mix * k)
    atmo_level = min(0.75, mode.atmosphere_mix * k)
    d1 = int(55 + rev_level * 90)
    d2 = int(120 + rev_level * 160)
    d3 = int(210 + atmo_level * 220)
