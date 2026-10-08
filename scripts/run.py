#!/usr/bin/env python3
"""Persistent ACE-Step notebook runner; stops only on user interrupt or platform shutdown."""
from __future__ import annotations
import os
import ctypes
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SERVER_PORT = int(os.getenv("ACE_SERVER_PORT", "8085"))
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
children = []
stopping = False


def die_with_parent():
    """Linux: ask kernel to terminate child if notebook runner vanishes."""
    try:
        if sys.platform.startswith("linux"):
            libc = ctypes.CDLL(None)
            libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


def prepare_env():
    e = os.environ.copy()
    e["ACE_SERVER_URL"] = SERVER_URL
    e["GRADIO_PORT"] = str(GRADIO_PORT)
    e["GGML_BACKEND"] = e.get("ACE_GPU", "CUDA0")
    e["OMP_NUM_THREADS"] = e.get("OMP_NUM_THREADS", "4")
    e["PYTHONUNBUFFERED"] = "1"
    packaged = ROOT / "runtime" / "build"
    local = ROOT / "runtime" / "acestep-cpp" / "build"
    runtime13 = (
        Path(sys.prefix) / "lib" /
        f"python{sys.version_info.major}.{sys.version_info.minor}" /
        "site-packages/nvidia/cu13/lib"
    )
    paths = [str(p) for p in (packaged, local, runtime13) if p.is_dir()]
    previous = e.get("LD_LIBRARY_PATH", "")
    if previous:
        paths.append(previous)
    e["LD_LIBRARY_PATH"] = ":".join(paths)
    return e

def health():
    try:
        with urllib.request.urlopen(SERVER_URL + "/health", timeout=3) as r:
            return r.status == 200 and b'"ok"' in r.read(300)
    except Exception:
        return False

def engine_bin():
    choices = [
        ROOT / "runtime/build/ace-server",
        ROOT / "runtime/acestep-cpp/build/ace-server"
    ]
    return next((p for p in choices if p.is_file()), None)

def spawn_server(env):
    exe = engine_bin()
    if exe is None:
        raise RuntimeError("Falta ace-server. Ejecuta scripts/install.py primero.")
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    logfile = logs / "ace-server.log"
    cmd = [
        str(exe), "--models", str(ROOT / "models"),
        "--host", "127.0.0.1", "--port", str(SERVER_PORT),
        "--max-batch", "1", "--no-fa", "--clamp-fp16",
    ]
    print("[STUDIO] Iniciando ACE-Step GGUF sobre GPU...", flush=True)
    with logfile.open("ab", buffering=0) as out:
        p = subprocess.Popen(
            cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
            preexec_fn=die_with_parent,
        )
    children.append(p)
    until = time.monotonic() + 90
    while time.monotonic() < until:
        if p.poll() is not None:
            raise RuntimeError(
                f"Motor terminó con código {p.returncode}. "
                f"Consulta logs/ace-server.log."
            )
        if health():
            print("[STUDIO] Motor activo.", flush=True)
            return p
        time.sleep(2)
    raise RuntimeError("ACE-Step no abrió el servidor. Consulta logs/ace-server.log.")

def spawn_gradio(env):
    print("[STUDIO] Abriendo Gradio con siete pestañas...", flush=True)
    p = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "scripts/gradio_guard.py")],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        start_new_session=True,
        preexec_fn=die_with_parent,
    )
    children.append(p)
    return p

def stop_owned(p):
    if p is None or p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        p.wait(timeout=7)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(timeout=5)

def on_stop(signum, _):
    global stopping
    stopping = True
    print("\n[STUDIO] Detención manual solicitada.", flush=True)
    raise KeyboardInterrupt()

def run():
    signal.signal(signal.SIGINT, on_stop)
    signal.signal(signal.SIGTERM, on_stop)
    env = prepare_env()
    print("ACE-STEP KAGGLE STUDIO | Run All -> GRADIO PERSISTENTE", flush=True)
    print("No hay temporizador. Para detener: pulsa Stop / Interrupt.", flush=True)
    print("Kaggle y Colab pueden cerrar su sesión por límites externos.", flush=True)
    server, ui = None, None
    try:
        while not stopping:
            if server is None or server.poll() is not None:
                if server is not None:
                    print("[STUDIO] Reiniciando motor cerrado inesperadamente.", flush=True)
                    time.sleep(10)
                server = spawn_server(env)
            if ui is None or ui.poll() is not None:
                if ui is not None:
                    print("[STUDIO] Reiniciando Gradio cerrado inesperadamente.", flush=True)
                    time.sleep(5)
                ui = spawn_gradio(env)
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        # Never signal other notebooks or Lilith services: stop only own children.
        for proc in reversed(children):
            stop_owned(proc)
        print("[STUDIO] Detenido por el usuario.", flush=True)

if __name__ == "__main__":
    run()
