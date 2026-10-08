"""Small MP3 listening previews while preserving original lossless WAV downloads."""
from __future__ import annotations

from pathlib import Path
import subprocess
import time
import soundfile as sf

PREVIEW_BITRATE_KBPS = 128


def make_preview(wav_file: str | Path) -> tuple[str, str]:
    """Convert final WAV to small 128 kb/s MP3 for playback.

    Do not rewrite or remove WAV. Gradio's Audio(format='mp3') uses the
    compressed asset. A separate File component exposes the untouched WAV.
    """
    original=Path(wav_file).resolve()
    if not original.is_file() or original.suffix.lower() != ".wav":
        raise ValueError("No se encontró el WAV original para crear la vista previa.")
    preview=original.with_suffix(".preview.mp3")
    if (preview.exists() and preview.stat().st_size>1024
            and preview.stat().st_mtime >= original.stat().st_mtime):
        return str(preview), size_report(original,preview)
    args=[
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
        "-i",str(original),"-vn",
        "-map","0:a:0","-codec:a","libmp3lame",
        "-b:a",f"{PREVIEW_BITRATE_KBPS}k","-ac","2","-ar","48000",
        "-map_metadata","-1",str(preview),
    ]
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=240)
    except subprocess.TimeoutExpired as exc:
        preview.unlink(missing_ok=True)
        raise RuntimeError("La vista previa MP3 excedió el tiempo de conversión. "
                           "El WAV original sigue guardado.") from exc
    if result.returncode or not preview.exists() or preview.stat().st_size<1024:
        preview.unlink(missing_ok=True)
        raise RuntimeError("No se pudo comprimir el MP3: "+result.stderr[-350:])
    duration_wav=sf.info(original).duration
    duration_mp3=sf.info(preview).duration
    if abs(duration_wav-duration_mp3)>1:
        preview.unlink(missing_ok=True)
        raise RuntimeError("La vista previa quedó incompleta: "
                           f"{duration_wav:.1f}s WAV frente a {duration_mp3:.1f}s MP3.")
    return str(preview),size_report(original,preview)


def size_report(wav: Path,mp3: Path) -> str:
    wav_mb=wav.stat().st_size/(1024*1024)
    mp3_mb=mp3.stat().st_size/(1024*1024)
    saving=max(0,100*(1-mp3_mb/wav_mb)) if wav_mb else 0
    return (f"Vista previa MP3 {PREVIEW_BITRATE_KBPS} kbps: {mp3_mb:.1f} MB "
            f"vs WAV sin pérdida: {wav_mb:.1f} MB ({saving:.0f}% menos). "
            "El WAV original se conserva y solo se descarga al elegirlo.")


def preview_outputs(wav_file: str | Path,message: str) -> tuple[str,str,str]:
    mp3,info=make_preview(wav_file)
    return mp3,str(Path(wav_file).resolve()),message+"\n"+info
