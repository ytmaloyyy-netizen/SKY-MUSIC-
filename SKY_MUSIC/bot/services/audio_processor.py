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
class AudioTransformParams:
    preset_name: str
    speed_factor: float = 1.0          # 1.0 = оригинал, 0.8 = замедление на 20%, 1.25 = ускорение на 25%
    pitch_semitones: float = 0.0       # сдвиг тона в полутонах
    preserve_pitch: bool = False       # если True — при изменении скорости компенсируем высоту тона
    bass_db: float = 0.0               # усиление НЧ (дБ)
    reverb_amount: float = 0.0         # интенсивность реверберации [0.0 .. 1.0]
    output_format: str = "mp3"

    def to_json(self) -> str:
        return json.dumps(
            {
                "preset": self.preset_name,
                "speed": self.speed_factor,
                "pitch_semitones": self.pitch_semitones,
                "preserve_pitch": self.preserve_pitch,
                "bass_db": self.bass_db,
                "reverb": self.reverb_amount,
                "format": self.output_format,
            },
            ensure_ascii=False,
        )


PRESETS: dict[str, AudioTransformParams] = {
    "slowed": AudioTransformParams(
        preset_name="🐢 Slowed",
        speed_factor=0.84,
        pitch_semitones=-1.5,
        preserve_pitch=False,
        bass_db=2.0,
        reverb_amount=0.15,
    ),
    "ultra_slowed": AudioTransformParams(
        preset_name="🐌 Ultra Slowed",
        speed_factor=0.68,
        pitch_semitones=-3.5,
        preserve_pitch=False,
        bass_db=4.0,
        reverb_amount=0.35,
    ),
    "speed_up": AudioTransformParams(
        preset_name="⚡ Speed Up",
        speed_factor=1.20,
        pitch_semitones=1.5,
        preserve_pitch=False,
        bass_db=1.5,
        reverb_amount=0.0,
    ),
    "ultra_speed_up": AudioTransformParams(
        preset_name="🚀 Ultra Speed Up",
        speed_factor=1.40,
        pitch_semitones=3.0,
        preserve_pitch=False,
        bass_db=1.0,
        reverb_amount=0.0,
    ),
    "nightcore": AudioTransformParams(
        preset_name="🎧 Nightcore",
        speed_factor=1.28,
        pitch_semitones=4.0,
        preserve_pitch=False,
        bass_db=2.5,
        reverb_amount=0.05,
    ),
    "slowed_reverb": AudioTransformParams(
        preset_name="🌙 Slowed + Reverb",
        speed_factor=0.82,
        pitch_semitones=-2.0,
        preserve_pitch=False,
        bass_db=3.5,
        reverb_amount=0.65,
    ),
    "bass_boost": AudioTransformParams(
        preset_name="🔊 Bass Boost",
        speed_factor=1.0,
        pitch_semitones=0.0,
        preserve_pitch=True,
        bass_db=9.0,
        reverb_amount=0.0,
    ),
    "pitch_up": AudioTransformParams(
        preset_name="🎼 Pitch Up",
        speed_factor=1.0,
        pitch_semitones=3.0,
        preserve_pitch=False,
        bass_db=0.0,
        reverb_amount=0.0,
    ),
    "pitch_down": AudioTransformParams(
        preset_name="🎼 Pitch Down",
        speed_factor=1.0,
        pitch_semitones=-3.0,
        preserve_pitch=False,
        bass_db=0.0,
        reverb_amount=0.0,
    ),
    "original": AudioTransformParams(
        preset_name="🔄 Вернуть оригинал",
        speed_factor=1.0,
        pitch_semitones=0.0,
        preserve_pitch=True,
        bass_db=0.0,
        reverb_amount=0.0,
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
        raise RuntimeError(f"Ошибка FFmpeg: {' | '.join(err_tail)}")


def _build_reverb_filter(amount: float) -> list[str]:
    clamped = max(0.0, min(1.0, amount))
    if clamped <= 0.01:
        return []
    in_gain = round(0.85 - clamped * 0.25, 3)
    out_gain = round(0.85 - clamped * 0.2, 3)
    # Многокаскадное эхо для плотной реверберации в FFmpeg
    d1 = int(45 + clamped * 55)
    d2 = int(95 + clamped * 115)
    dec1 = round(0.22 + clamped * 0.32, 3)
    dec2 = round(0.16 + clamped * 0.28, 3)
    return [f"aecho={in_gain}:{out_gain}:{d1}|{d2}:{dec1}|{dec2}"]


def _process_sync(input_path: Path, output_path: Path, params: AudioTransformParams) -> Path:
    work_dir = output_path.parent
    extracted_wav = work_dir / "extracted_input.wav"
    dsp_wav = work_dir / "dsp_out.wav"

    # 1. Приводим любой входной аудио/видео файл к единому WAV PCM для точного DSP
    _run_ffmpeg(["-i", str(input_path), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(extracted_wav)])

    y, sr = librosa.load(str(extracted_wav), sr=44100, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y], axis=0)

    speed = max(0.4, min(2.2, float(params.speed_factor)))
    pitch = float(params.pitch_semitones)

    # Если включено сохранение высоты голоса при изменении скорости — компенсируем питч
    if params.preserve_pitch and abs(speed - 1.0) > 1e-4:
        # rate > 1 ускоряет, но повышает тон; чтобы сохранить высоту голоса, pitch_shift = -12*log2(speed)
        pitch = -12.0 * float(np.log2(speed))

    channels_out: list[np.ndarray] = []
    for ch in range(y.shape[0]):
        sig = y[ch]
        if abs(speed - 1.0) > 1e-4:
            sig = librosa.effects.time_stretch(sig, rate=speed)
        if abs(pitch) > 1e-4:
            sig = librosa.effects.pitch_shift(sig, sr=sr, n_steps=pitch)
        channels_out.append(sig)

    min_len = min(len(c) for c in channels_out)
    stereo = np.stack([c[:min_len] for c in channels_out], axis=0)
    # stereo shape: (2, N) -> soundfile ожидает (N, 2)
    sf.write(str(dsp_wav), stereo.T, sr, subtype="PCM_16")

    # 2. Финальная обработка басов, реверберации и экспорт в целевой формат через FFmpeg
    filters: list[str] = []
    if abs(params.bass_db) > 0.05:
        filters.append(f"bass=g={round(params.bass_db, 2)}:f=110:w=0.6")
    filters.extend(_build_reverb_filter(params.reverb_amount))
    filters.append("alimiter=limit=0.95")

    ext = params.output_format.lower().lstrip(".")
    final_file = output_path.with_suffix(f".{ext}")

    ffmpeg_args = ["-i", str(dsp_wav), "-af", ",".join(filters)]
    if ext == "mp3":
        ffmpeg_args.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
    elif ext == "flac":
        ffmpeg_args.extend(["-c:a", "flac"])
    elif ext == "m4a":
        ffmpeg_args.extend(["-c:a", "aac", "-b:a", "256k"])
    elif ext == "ogg":
        ffmpeg_args.extend(["-c:a", "libvorbis", "-q:a", "6"])
    else:
        ffmpeg_args.extend(["-c:a", "pcm_s16le"])

    ffmpeg_args.append(str(final_file))
    _run_ffmpeg(ffmpeg_args)
    return final_file


async def process_audio_file(
    input_path: Path,
    output_path: Path,
    params: AudioTransformParams,
) -> Path:
    return await asyncio.to_thread(_process_sync, input_path, output_path, params)
