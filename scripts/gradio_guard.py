#!/usr/bin/env python3
"""Gradio guardian: closes its Gradio process group on Stop or notebook-runner death.

The supervisor sends this wrapper SIGTERM via Linux PR_SET_PDEATHSIG even
if its parent is force-killed; the wrapper cleans up Gradio's share tunnel.
"""
from __future__ import annotations
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
child=None
starting_parent=os.getppid()

def stop_signal(signum,frame):
    raise KeyboardInterrupt()

def stop_group():
    global child
    if child is None or child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=5)

def main():
    global child
    signal.signal(signal.SIGTERM,stop_signal)
    signal.signal(signal.SIGINT,stop_signal)
    try:
        child=subprocess.Popen(
            [sys.executable,"-u",str(ROOT/"studio_tabs.py")],
            cwd=ROOT,env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        while True:
            if child.poll() is not None:
                sys.exit(child.returncode or 0)
            if os.getppid()!=starting_parent:
                raise KeyboardInterrupt()
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        stop_group()

if __name__=="__main__":
    main()
