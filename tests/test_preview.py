"""Preview regression tests; offline CPU/ffmpeg, never touches existing Gradio."""
from __future__ import annotations
import hashlib
from pathlib import Path
import tempfile
import unittest
import wave

try:
    import soundfile as sf
except ImportError:
    sf = None

from studio_preview import make_preview, preview_outputs


@unittest.skipUnless(sf is not None, "soundfile required")
class PreviewTests(unittest.TestCase):
    def test_compressed_preview_preserves_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "song.wav"
            with wave.open(str(source),"wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(48000)
                # 5 seconds stereo PCM 16 bit, deterministic saw signal.
                data = bytearray()
                for i in range(48000 * 5):
                    value = int(8500 * ((i % 80) / 80 - 0.5))
                    data.extend(int(value).to_bytes(2,"little",signed=True)*2)
                handle.writeframes(data)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            preview, report = make_preview(source)
            preview_file = Path(preview)
            self.assertEqual(preview_file.suffix,".mp3")
            self.assertLess(preview_file.stat().st_size,source.stat().st_size * .20)
            self.assertAlmostEqual(sf.info(preview_file).duration,5.0,delta=0.15)
            self.assertEqual(digest,hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertIn("128 kbps",report)
            # The same preview is reused, not transcoded a second time.
            second,_=make_preview(source)
            self.assertEqual(preview,second)
            result=preview_outputs(source,"OK")
            self.assertEqual(len(result),3)
            self.assertEqual(result[0],str(preview_file))
            self.assertEqual(result[1],str(source))
            self.assertIn("OK",result[2])

    def test_seven_tabs_have_both_outputs(self):
        from studio_tabs import app
        data=app.get_config_file()
        preview=[component for component in data["components"]
                 if component["type"]=="audio" and
                 "Vista previa comprimida" in str(component["props"].get("label"))]
        lossless=[component for component in data["components"]
                  if component["type"]=="file" and
                  "Descargar WAV original" in str(component["props"].get("label"))]
        self.assertEqual(len(preview),7)
        self.assertEqual(len(lossless),7)
        self.assertTrue(all(x["props"]["format"]=="mp3" for x in preview))
        funcs={"create_song_preview","cover_creative","cover_faithful",
               "repaint","add_track","extract_track","complete_track"}
        outputs=[len(d["outputs"]) for d in data["dependencies"]
                 if d.get("api_name") in funcs]
        self.assertEqual(outputs,[3]*7)


if __name__=="__main__":
    unittest.main()
