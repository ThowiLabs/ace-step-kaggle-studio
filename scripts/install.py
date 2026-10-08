#!/usr/bin/env python3
"""Install ACE-Step GGUF weights and a CUDA engine, without relying on an existing Kaggle session."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

REPO = Path(__file__).resolve().parents[1]
BIN_RELEASE = (
    "https://github.com/animede/momo-song-v4/releases/download/v0.1.0-rc1/"
    "acestep.cpp-linux-x86_64-cuda.tar.gz"
)
BIN_SHA256 = "5d56acc372d1ea0b54f66202967fb5b0bd8a06220a02aeaa06a58f8b6524c03d"
GGUF_REPO = "CC-TM/ACE-Step-1.5-GGUF"
MODELS = [
    "Qwen3-Embedding-0.6B-Q8_0.gguf",
    "acestep-5Hz-lm-4B-Q8_0.gguf",
    "acestep-v15-xl-turbo-Q8_0.gguf",
    "acestep-v15-base-Q8_0.gguf",
    "vae-BF16.gguf",
]

def gpu_info() -> tuple[str, int]:
    # Kaggle can provide CUDA GPUs even when nvidia-smi is not on PATH.
    # Confirm actual CUDA access with torch, and read kernel driver as fallback.
    try:
        import torch
        has_cuda=bool(torch.cuda.is_available() and torch.cuda.device_count()>0)
    except ImportError:
        has_cuda=False
    if not has_cuda:
        raise RuntimeError("Se necesita GPU NVIDIA. Activa GPU en Kaggle/Colab y vuelve a Run All.")
    driver=""
    binary=shutil.which("nvidia-smi")
    if binary:
        result=subprocess.run(
            [binary,"--query-gpu=driver_version","--format=csv,noheader"],
            text=True,capture_output=True,timeout=20,
        )
        if result.returncode==0 and result.stdout.strip():
            driver=result.stdout.splitlines()[0].strip()
    if not driver:
        info=Path("/proc/driver/nvidia/version")
        if info.is_file():
            m=re.search(r"\b(\d{3}\.\d+(?:\.\d+)?)\b",info.read_text())
            if m:
                driver=m.group(1)
    match=re.match(r"(\d+)",driver)
    if not match:
        raise RuntimeError("No pude detectar el controlador NVIDIA. Driver: "+repr(driver))
    return driver,int(match.group(1))

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fd:
        for chunk in iter(lambda: fd.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def install_prebuilt() -> None:
    import requests
    runtime = REPO / "runtime"
    archive = REPO / "runtime" / "ace-linux-cuda13.tar.gz"
    runtime.mkdir(parents=True, exist_ok=True)
    binary = runtime / "build" / "ace-server"
    if binary.is_file():
        print("[ENGINE] Binario CUDA precompilado ya existe; se reutiliza.", flush=True)
        return
    if not archive.is_file() or sha256(archive) != BIN_SHA256:
        archive.unlink(missing_ok=True)
        print("[ENGINE] Descargando paquete Linux/CUDA precompilado ...", flush=True)
        response = requests.get(BIN_RELEASE, stream=True, timeout=(30, 90))
        response.raise_for_status()
        with archive.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
    digest = sha256(archive)
    if digest != BIN_SHA256:
        raise RuntimeError(
            "SHA-256 del motor no coincide con la versión probada. "
            "No ejecutaré un binario de origen dudoso."
        )
    print("[ENGINE] SHA-256 verificado:", digest, flush=True)
    # Only accepted in-repo paths; reject symlinks and path traversal.
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf.getmembers():
            target = (runtime / member.name).resolve()
            if not target.is_relative_to(runtime.resolve()):
                raise RuntimeError("Archivo malicioso en el tar: " + member.name)
            if member.issym() or member.islnk():
                # The release contains normal soname symlinks inside build/;
                # validate the destination after resolving in the extracted folder.
                if Path(member.linkname).is_absolute() or ".." in Path(member.linkname).parts:
                    raise RuntimeError("Enlace sospechoso en tar: " + member.name)
        tf.extractall(runtime, filter="data")
    if not binary.is_file():
        raise RuntimeError("El paquete CUDA no contiene build/ace-server.")
    binary.chmod(binary.stat().st_mode | 0o111)
    print("[ENGINE] ace-server CUDA13 listo.", flush=True)

def install_cuda13_runtime() -> None:
    print("[CUDA] Instalando librerías runtime CUDA 13.0 sin cambiar driver...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "nvidia-cuda-runtime==13.0.96",
         "nvidia-cublas==13.0.2.14"],
        check=True,
    )

def detect_compute_capability() -> str:
    try:
        import torch
        major, minor = torch.cuda.get_device_capability(0)
        return f"{major}{minor}"
    except Exception:
        return "75"

def compile_fallback() -> None:
    """Older Colab drivers cannot load CUDA13 prebuilt. Build with its native nvcc."""
    if not shutil.which("cmake") or not shutil.which("git") or not shutil.which("nvcc"):
        raise RuntimeError(
            "El driver es anterior a R580 y el entorno no incluye nvcc/cmake/git. "
            "Colab requiere CUDA Toolkit para compilar la variante compatible. "
            "Activa un runtime GPU con driver NVIDIA R580+ o instala CUDA Toolkit."
        )
    source = REPO / "runtime" / "acestep-cpp"
    binary = source / "build" / "ace-server"
    if binary.exists():
        print("[ENGINE] Binario compilado localmente ya existe.", flush=True)
        return
    if not source.exists():
        print("[ENGINE] Descargando código fuente acestep.cpp (CUDA local)...", flush=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--recurse-submodules",
             "https://github.com/ServeurpersoCom/acestep.cpp.git", str(source)],
            check=True,
        )
    sm = detect_compute_capability()
    print(f"[ENGINE] Compilando CUDA para SM{sm}. La primera vez puede tardar bastante.", flush=True)
    build = source / "build"
    subprocess.run(
        ["cmake", "-S", str(source), "-B", str(build),
         "-DGGML_CUDA=ON", "-DGGML_CUDA_NO_VMM=ON",
         "-DGGML_CUDA_NCCL=OFF",
         "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_CUDA_ARCHITECTURES={sm}"],
        check=True,
    )
    # Conservador en Kaggle/Colab para evitar quedarnos sin RAM.
    subprocess.run(["cmake", "--build", str(build), "--target", "ace-server", "-j", "2"], check=True)
    if not binary.is_file():
        raise RuntimeError("No se generó el binario local de ACE-Step.")

def download_models() -> None:
    from huggingface_hub import hf_hub_download
    target = REPO / "models"
    target.mkdir(parents=True, exist_ok=True)
    for i, filename in enumerate(MODELS, 1):
        p = target / filename
        if p.is_file() and p.stat().st_size > 10_000_000:
            print(f"[{i}/{len(MODELS)}] {filename}: ya descargado.",flush=True)
            continue
        print(f"[{i}/{len(MODELS)}] Descargando {filename}...", flush=True)
        result = hf_hub_download(
            repo_id=GGUF_REPO,
            filename=filename,
            local_dir=str(target),
        )
        if Path(result).stat().st_size < 10_000_000:
            raise RuntimeError("Descarga de modelo incompleta: " + filename)
        print(f"     Listo: {Path(result).stat().st_size/1e9:.2f} GB", flush=True)

def check() -> None:
    driver, major = gpu_info()
    print(f"[GPU] NVIDIA Driver {driver}",flush=True)
    models = REPO / "models"
    for name in MODELS:
        p = models/name
        print("[MODEL]", "OK" if p.exists() else "FALTA", name)
    if major >= 580:
        print("[ENGINE]", REPO/"runtime/build/ace-server")
    else:
        print("[ENGINE] Compilación CUDA local necesaria para el controlador actual.")
    print("[STUDIO] Código local disponible:",(REPO/"studio_tabs.py").exists())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true",help="Check only; do not install")
    args=parser.parse_args()
    if args.check:
        check()
        return
    driver,major=gpu_info()
    print(f"[GPU] Driver {driver}; CUDA13 precompilado {'compatible' if major>=580 else 'NO compatible'}.",flush=True)
    if major>=580:
        install_cuda13_runtime()
        install_prebuilt()
    else:
        compile_fallback()
    download_models()
    print("\n[OK] ACE-Step XL Q8, LM 4B Q8, Base Q8 y VAE disponibles.", flush=True)

if __name__ == "__main__":
    main()
