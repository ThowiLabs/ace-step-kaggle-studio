#!/usr/bin/env python3
"""Generar cuadernos Kaggle y Colab que descargan el proyecto desde GitHub."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/ThowiLabs/ace-step-kaggle-studio.git"
BRANCH = "main"
VERSION = "1.0.5"


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": (source.strip() + "\n").splitlines(keepends=True),
    }


def markdown(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": (source.strip() + "\n").splitlines(keepends=True),
    }


def build(platform: str) -> Path:
    location = (
        "/kaggle/working/ace-step-kaggle-studio"
        if platform == "Kaggle"
        else "/content/ace-step-kaggle-studio"
    )
    cells = [
        markdown(
            "# ACE-Step Kaggle Studio\n\n"
            "Generación y edición musical con ACE-Step 1.5 GGUF."
        ),
        code_cell(
            f"""
from pathlib import Path
import subprocess

PROJECT = Path({location!r})
REPOSITORY = {REPOSITORY!r}
BRANCH = {BRANCH!r}

if not (PROJECT / ".git").is_dir():
    if PROJECT.exists() and any(PROJECT.iterdir()):
        raise RuntimeError(f"La carpeta {{PROJECT}} ya existe y no es un repositorio Git.")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", BRANCH, REPOSITORY, str(PROJECT)],
        check=True,
    )
else:
    origin = subprocess.check_output(
        ["git", "-C", str(PROJECT), "remote", "get-url", "origin"],
        text=True,
    ).strip()
    if origin.rstrip("/").removesuffix(".git") != REPOSITORY.removesuffix(".git"):
        raise RuntimeError(f"El repositorio existente tiene otro origen: {{origin}}")
    subprocess.run(
        ["git", "-C", str(PROJECT), "pull", "--ff-only", "origin", BRANCH],
        check=True,
    )

print("Proyecto:", PROJECT)
"""
        ),
        code_cell(
            """
import subprocess
import sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "-r", str(PROJECT / "requirements.txt")],
    check=True,
)
subprocess.run(
    [sys.executable, "-u", str(PROJECT / "scripts/install.py")],
    check=True,
)
"""
        ),
        code_cell(
            """
import subprocess
import sys

subprocess.run(
    [sys.executable, "-u", str(PROJECT / "scripts/run.py")],
    cwd=str(PROJECT),
    check=True,
)
"""
        ),
    ]
    result = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3", "language": "python", "name": "python3"
            },
            "language_info": {"name": "python"},
            "accelerator": "GPU",
            "ace_step_platform": platform,
            "ace_step_studio_version": VERSION,
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    target = ROOT / "notebooks" / f"ACE-Step-Kaggle-Studio-{platform}.ipynb"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target.name, target.stat().st_size, "bytes")
    return target


if __name__ == "__main__":
    build("Kaggle")
    build("Colab")
