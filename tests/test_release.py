"""Offline release tests; no GPU, model download, or server required."""
from __future__ import annotations
import ast
import base64
from io import BytesIO
import json
from pathlib import Path
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_all_python_sources_compile(self):
        files=[
            *ROOT.glob("studio_*.py"),
            *ROOT.glob("scripts/*.py"),
        ]
        self.assertGreaterEqual(len(files),7)
        for p in files:
            compile(p.read_text(),str(p),"exec")

    def test_two_self_contained_notebooks(self):
        for platform in ["Kaggle","Colab"]:
            nb=ROOT/"notebooks"/f"ACE-Step-Kaggle-Studio-{platform}.ipynb"
            self.assertTrue(nb.exists(),str(nb))
            data=json.loads(nb.read_text())
            self.assertEqual(data["nbformat"],4)
            self.assertEqual(len(data["cells"]),4)
            bootstrap="".join(data["cells"][1]["source"])
            self.assertIn("ARCHIVE",bootstrap)
            arc_line=bootstrap.split("ARCHIVE",1)[1].split("=",1)[1].splitlines()[0]
            encoded=ast.literal_eval(arc_line)
            with ZipFile(BytesIO(base64.b64decode(encoded))) as z:
                names=set(z.namelist())
                self.assertIn("studio_tabs.py",names)
                self.assertIn("studio_smart.py",names)
                self.assertIn("scripts/run.py",names)
                self.assertIn("scripts/install.py",names)
                self.assertIn("requirements.txt",names)
                self.assertIn("while not stopping",z.read("scripts/run.py").decode())
            last="".join(data["cells"][-1]["source"])
            self.assertIn("scripts/run.py",last)
            self.assertNotIn("Batch",last)

    def test_tabbed_studio_has_seven_modes(self):
        s=(ROOT/"studio_tabs.py").read_text()
        self.assertEqual(s.count("with gr.Tab("),7)
        for operation in [
            "cover","cover-nofsq","repaint","lego","extract","complete"
        ]:
            self.assertIn('"' + operation + '"',s)

    def test_run_script_does_not_kill_foreign_services(self):
        s=(ROOT/"scripts/run.py").read_text()
        self.assertIn("start_new_session=True",s)
        self.assertIn("os.killpg(p.pid, signal.SIGTERM)",s)
        self.assertIn("while not stopping",s)
        self.assertNotIn("pkill",s.replace("Never use pkill",""))
        self.assertNotIn("killall",s)
        self.assertNotIn("max_runtime_seconds",s)

    def test_downloads_required_models_and_checksum(self):
        s=(ROOT/"scripts/install.py").read_text()
        for name in [
            "acestep-v15-xl-turbo-Q8_0.gguf",
            "acestep-v15-base-Q8_0.gguf",
            "acestep-5Hz-lm-4B-Q8_0.gguf",
            "Qwen3-Embedding-0.6B-Q8_0.gguf",
            "vae-BF16.gguf",
        ]:
            self.assertIn(name,s)
        self.assertIn("BIN_SHA256",s)
        self.assertIn("sha256(archive)",s)
        self.assertIn("compile_fallback",s)


if __name__=="__main__":
    unittest.main()
