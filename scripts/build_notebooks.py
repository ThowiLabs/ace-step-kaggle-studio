#!/usr/bin/env python3
"""Genera notebooks autónomos para Kaggle y Google Colab."""
from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    "studio_gguf.py",
    "studio_smart.py",
    "studio_diagnostic.py",
    "studio_tabs.py",
    "studio_preview.py",
    "requirements.txt",
    "scripts/install.py",
    "scripts/run.py",
    "scripts/gradio_guard.py",
]


def bundle() -> str:
    content = BytesIO()
    with ZipFile(content, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for filename in SOURCE_FILES:
            archive.write(ROOT / filename, arcname=filename)
    return base64.b64encode(content.getvalue()).decode("ascii")


def code_cell(source: str, *, collapse: bool = False) -> dict:
    metadata = {"jupyter": {"source_hidden": True}} if collapse else {}
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": metadata,
        "outputs": [],
        "source": (source.strip() + "\n").splitlines(keepends=True),
    }


def markdown(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": (source.strip() + "\n").splitlines(keepends=True),
    }


def notebook(platform: str, encoded: str) -> Path:
    workdir = (
        "/kaggle/working/ace-step-kaggle-studio"
        if platform == "Kaggle"
        else "/content/ace-step-kaggle-studio"
    )
    cells = [
        markdown(
            "# ACE-Step Kaggle Studio\n\n"
            "Music generation, covers, remixes and audio editing with ACE-Step 1.5 GGUF."
        ),
        code_cell(
            f"""
from pathlib import Path
import base64
import io
import os
import zipfile

PROJECT = Path({workdir!r})
PROJECT.mkdir(parents=True, exist_ok=True)
ARCHIVE = {encoded!r}
with zipfile.ZipFile(io.BytesIO(base64.b64decode(ARCHIVE))) as source:
    for filename in source.namelist():
        output = (PROJECT / filename).resolve()
        if not output.is_relative_to(PROJECT.resolve()):
            raise RuntimeError("Invalid archive entry.")
    source.extractall(PROJECT)

os.chdir(PROJECT)
print("ACE-Step Kaggle Studio")
""",
            collapse=True,
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
    data = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
            "accelerator": "GPU",
            "ace_step_platform": platform,
            "ace_step_studio_version": "1.0.3",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    output = ROOT / "notebooks" / f"ACE-Step-Kaggle-Studio-{platform}.ipynb"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Created", output.name, "|", output.stat().st_size, "bytes")
    return output


if __name__ == "__main__":
    encoded = bundle()
    notebook("Kaggle", encoded)
    notebook("Colab", encoded)
