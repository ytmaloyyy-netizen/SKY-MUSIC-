from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf


SUPPORTED_VOCAL_MODES = {
    "no_vocals": "🎤 Убрать вокал",
    "vocals_only": "🎙️ Оставить только вокал",
    "drums_only": "🥁 Оставить ударные",
    "instruments_only": "🎸 Оставить инструменты",
    "bass_only": "🎚️ Извлечь бас",
    "melody_only": "🎼 Извлечь мелодию",
    "all_stems": "🎹 Разделить музыку на дорожки",
}


def _run_cmd(args: list[str]) -> None:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err_tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        raise RuntimeError(f"Ошибка выполнения команды ({args[0]}): {' | '.join(err_tail)}")


def _load_stem(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), always_2d=True)
    return audio.astype(np.float32), int(sr)


def _save_mp3(audio: np.ndarray, sr: int, work_dir: Path, stem_name: str) -> Path:
    clipped = np.clip(audio, -0.98, 0.98)
    raw_wav = work_dir / f"{stem_name}_raw.wav"
    out_mp3 = work_dir / f"{stem_name}.mp3"
    sf.write(str(raw_wav), clipped, sr, subtype="PCM_16")
    _run_cmd(["ffmpeg", "-y", "-i", str(raw_wav), "-c:a", "libmp3lame", "-b:a", "320k", str(out_mp3)])
    return out_mp3


def _separate_sync(input_path: Path, work_dir: Path, mode: str, model_name: str = "htdemucs") -> list[tuple[str, Path]]:
    if mode not in SUPPORTED_VOCAL_MODES:
        raise ValueError(f"Неизвестный режим разделения: {mode}")

    prepared_wav = work_dir / "prepared_for_demucs.wav"
    _run_cmd(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le",
            str(prepared_wav),
        ]
    )

    demucs_out_root = work_dir / "demucs_stems"
    demucs_out_root.mkdir(parents=True, exist_ok=True)

    # Запуск модели Demucs (использует GPU при наличии, иначе CPU)
    _run_cmd(
        [
            "demucs",
            "-n", model_name,
            "-o", str(demucs_out_root),
            str(prepared_wav),
        ]
    )

    track_dir = demucs_out_root / model_name / prepared_wav.stem
    vocals_path = track_dir / "vocals.wav"
    drums_path = track_dir / "drums.wav"
    bass_path = track_dir / "bass.wav"
    other_path = track_dir / "other.wav"

    for p in (vocals_path, drums_path, bass_path, other_path):
        if not p.exists():
            raise RuntimeError(f"Demucs не создал дорожку: {p.name}")

    vocals, sr = _load_stem(vocals_path)
    drums, _ = _load_stem(drums_path)
    bass, _ = _load_stem(bass_path)
    other, _ = _load_stem(other_path)

    min_len = min(len(vocals), len(drums), len(bass), len(other))
    vocals = vocals[:min_len]
    drums = drums[:min_len]
    bass = bass[:min_len]
    other = other[:min_len]

    results: list[tuple[str, Path]] = []

    if mode == "no_vocals":
        inst = drums + bass + other
        results.append(("Без вокала (Instrumental)", _save_mp3(inst, sr, work_dir, "no_vocals")))
    elif mode == "vocals_only":
        results.append(("Только вокал (Vocals)", _save_mp3(vocals, sr, work_dir, "vocals_only")))
    elif mode == "drums_only":
        results.append(("Только ударные (Drums)", _save_mp3(drums, sr, work_dir, "drums_only")))
    elif mode == "instruments_only":
        results.append(("Инструменты (Other)", _save_mp3(other, sr, work_dir, "instruments_only")))
    elif mode == "bass_only":
        results.append(("Бас (Bass)", _save_mp3(bass, sr, work_dir, "bass_only")))
    elif mode == "melody_only":
        melody_wav = work_dir / "melody_raw.wav"
        melody_mp3 = work_dir / "melody_only.mp3"
        sf.write(str(melody_wav), np.clip(other, -0.98, 0.98), sr, subtype="PCM_16")
        _run_cmd(
            [
                "ffmpeg", "-y", "-i", str(melody_wav),
                "-af", "highpass=f=220,lowshelf=g=-4:f=300,alimiter=limit=0.95",
                "-c:a", "libmp3lame", "-b:a", "320k", str(melody_mp3),
            ]
        )
        results.append(("Мелодия (Melody)", melody_mp3))
    elif mode == "all_stems":
        results.append(("Вокал (Vocals)", _save_mp3(vocals, sr, work_dir, "stem_vocals")))
        results.append(("Ударные (Drums)", _save_mp3(drums, sr, work_dir, "stem_drums")))
        results.append(("Бас (Bass)", _save_mp3(bass, sr, work_dir, "stem_bass")))
        results.append(("Инструменты (Other)", _save_mp3(other, sr, work_dir, "stem_other")))

    return results


async def separate_audio_stems(
    input_path: Path,
    work_dir: Path,
    mode: str,
    model_name: str = "htdemucs",
) -> list[tuple[str, Path]]:
    return await asyncio.to_thread(_separate_sync, input_path, work_dir, mode, model_name)
