"""Offline release tests; no GPU, model download, or server required."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import run as studio_runner

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

    def test_notebooks_clonan_github_sin_codigo_embebido(self):
        repo = "https://github.com/ThowiLabs/ace-step-kaggle-studio.git"
        for platform, folder in [
            ("Kaggle", "/kaggle/working/ace-step-kaggle-studio"),
            ("Colab", "/content/ace-step-kaggle-studio"),
        ]:
            nb = ROOT / "notebooks" / f"ACE-Step-Kaggle-Studio-{platform}.ipynb"
            self.assertTrue(nb.exists(), str(nb))
            self.assertLess(nb.stat().st_size, 10_000, nb.name)
            data = json.loads(nb.read_text(encoding="utf-8"))
            self.assertEqual(data["nbformat"], 4)
            self.assertEqual(len(data["cells"]), 4)
            self.assertEqual(data["metadata"]["ace_step_studio_version"], "1.0.5")
            code = ["".join(cell["source"]) for cell in data["cells"][1:]]
            for source in code:
                ast.parse(source)
            self.assertIn(repo, code[0])
            self.assertIn(folder, code[0])
            self.assertIn('"git", "clone"', code[0])
            self.assertIn('"git", "-C", str(PROJECT), "pull"', code[0])
            self.assertIn("--ff-only", code[0])
            self.assertIn("requirements.txt", code[1])
            self.assertIn("scripts/install.py", code[1])
            self.assertIn("scripts/run.py", code[2])
            self.assertNotIn("BASE64", "".join(code).upper())
            self.assertNotIn("ARCHIVE", "".join(code))
            self.assertNotIn("zipfile", "".join(code))
            self.assertNotIn("studio_tabs.py", "".join(code))
            self.assertNotIn("studio_smart.py", "".join(code))

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

    def test_contexto_y_tareas_ponytail(self):
        contexto=ROOT/"contexto"
        tareas=ROOT/"tareas"
        self.assertTrue(contexto.is_dir())
        self.assertTrue(tareas.is_dir())
        archivos=list(contexto.glob("[0-9][0-9]-*.md"))
        self.assertGreaterEqual(len(archivos),2)
        for archivo in archivos:
            source=archivo.read_text(encoding="utf-8")
            for heading in (
                "# Fecha", "# Objetivo", "# Decisiones tomadas",
                "# Arquitectura actual", "# Librerías usadas",
                "# Archivos importantes modificados", "# Problemas encontrados",
                "# Soluciones implementadas", "# Pendientes", "# Próximos pasos",
            ):
                self.assertIn(heading,source,archivo.name)
        tasks=list(tareas.glob("*.md"))
        self.assertGreaterEqual(len(tasks),4)
        self.assertLessEqual(sum("en-proceso-" in f.name for f in tasks),1)
        self.assertTrue(all(
            "-completado-" in f.name or "-pendiente-" in f.name
            or "-en-proceso-" in f.name for f in tasks
        ))
        self.assertTrue((ROOT/".gitignore").exists())

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


class CudaRuntimeTests(unittest.TestCase):
    def test_cuda13_detecta_cu13_y_paquetes_separados(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            locations = [
                base / "site-packages/nvidia/cu13/lib/libcudart.so.13",
                base / "dist-packages/nvidia/cublas/lib/libcublas.so.13",
            ]
            for location in locations:
                location.parent.mkdir(parents=True, exist_ok=True)
                location.touch()
            (base / "site-packages/nvidia/cuda_runtime/lib").mkdir(
                parents=True, exist_ok=True
            )
            (base / "site-packages/nvidia/cuda_runtime/lib/libcudart.so.12").touch()
            found = studio_runner.cuda_library_dirs(
                [base / "site-packages", base / "dist-packages"]
            )
            self.assertEqual(set(found), {str(p.parent) for p in locations})

    def test_ld_library_path_incluye_cuda_y_rutas_existentes(self):
        with mock.patch.object(studio_runner, "cuda_library_dirs",
                               return_value=["/pkg/nvidia/cu13/lib"]):
            with mock.patch.dict("os.environ", {"LD_LIBRARY_PATH": "/custom/lib"}):
                env = studio_runner.prepare_env()
        self.assertIn("/pkg/nvidia/cu13/lib", env["LD_LIBRARY_PATH"].split(":"))
        self.assertIn("/custom/lib", env["LD_LIBRARY_PATH"].split(":"))

    def test_dependencias_faltantes_generan_error_claro(self):
        response = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="libcudart.so.13 => not found\\n", stderr=""
        )
        with mock.patch.object(studio_runner.subprocess, "run",
                               return_value=response):
            with self.assertRaisesRegex(RuntimeError, "libcudart.so.13"):
                studio_runner.check_engine_dependencies(
                    Path("/tmp/ace-server"), {}
                )

    def test_dependencias_encontradas_permiten_continuar(self):
        response = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="libcudart.so.13 => /pkg/libcudart.so.13\\n", stderr=""
        )
        with mock.patch.object(studio_runner.subprocess, "run",
                               return_value=response):
            studio_runner.check_engine_dependencies(Path("/tmp/ace-server"), {})


if __name__=="__main__":
    unittest.main()
