"""ACE-Step XL Q8 Gradio connected to the local GGUF CUDA backend."""
import email
import threading
import os
import time
import uuid
from pathlib import Path

import gradio as gr
import numpy as np
import requests
import soundfile as sf

API=os.environ.get("ACE_SERVER_URL", "http://127.0.0.1:8085")
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"outputs"
OUT.mkdir(exist_ok=True)
XL="acestep-v15-xl-turbo-Q8_0.gguf"
LM="acestep-5Hz-lm-4B-Q8_0.gguf"
LOCK=threading.Lock()


def request_job(endpoint, payload, progress=None):
    r=requests.post(API+endpoint,json=payload,timeout=35)
    r.raise_for_status()
    job=r.json().get("id")
    if job is None:
        raise gr.Error("Respuesta sin identificador de trabajo")
    started=time.monotonic()
    while True:
        state=requests.get(API+"/job",params={"id":job},timeout=20)
        state.raise_for_status()
        record=state.json()
        if record.get("status")=="done":
            break
        if record.get("status") in ("failed","cancelled"):
            raise gr.Error(f"{endpoint}: {record}")
        if time.monotonic()-started>1800:
            raise gr.Error("Se agotó el tiempo de espera del motor musical.")
        if progress:
            progress(0 if endpoint=="/lm" else 0.5,
                     desc=f"{endpoint}: {record.get('status')} · {int(time.monotonic()-started)} s")
        time.sleep(2)
    res=requests.get(API+"/job",params={"id":job,"result":"1"},timeout=120)
    res.raise_for_status()
    return res


def get_wav(response):
    mime=response.headers.get("Content-Type","")
    if response.content[:4]==b"RIFF":
        return response.content
    if "multipart/" not in mime:
        raise RuntimeError("Respuesta no musical: "+response.text[:250])
    msg=email.message_from_bytes(
        ("MIME-Version: 1.0\r\nContent-Type: "+mime+"\r\n\r\n").encode()
        +response.content)
    for part in msg.walk():
        binary=part.get_payload(decode=True)
        if binary and binary[:4]==b"RIFF":
            return binary
    raise RuntimeError("La respuesta del motor no contenía WAV.")


def generate(style,lyrics,seconds,bpm,seed,lang,progress=gr.Progress()):
    if not style.strip() or not lyrics.strip():
        raise gr.Error("Escribe el estilo y la letra, o [Instrumental].")
    try:
        with LOCK:
            progress(0,desc="Planificador 4B Q8: componiendo canción")
            payload={
                "caption":style.strip(),"lyrics":lyrics.strip(),
                "duration":int(seconds),"bpm":int(bpm),"seed":int(seed),
                "vocal_language":lang,"inference_steps":8,
                "guidance_scale":1.0,"shift":3.0,"use_cot_caption":False,
                "synth_model":XL,"lm_model":LM,"output_format":"wav16",
                "lm_temperature":0.85,"lm_cfg_scale":2.0,
                "synth_batch_size":1}
            rich=request_job("/lm",payload,progress).json()
            if not isinstance(rich,list) or not rich:
                raise RuntimeError("No se generó una composición.")
            rich[0].update(synth_model=XL,output_format="wav16")
            progress(0.5,desc="XL Turbo Q8: sintetizando audio")
            wav=get_wav(request_job("/synth",rich[0],progress))
            path=OUT/("ACE_XL_Q8_"+uuid.uuid4().hex[:8]+".wav")
            path.write_bytes(wav)
            try:
                audio,sr=sf.read(path,always_2d=True)
                if not len(audio) or not np.isfinite(audio).all():
                    raise RuntimeError("Audio sin muestras válidas.")
                rms=float(np.sqrt(np.mean(audio.astype(np.float64)**2)))
                saturated=float(np.mean(np.abs(audio)>0.995))
                if rms<0.0005 or saturated>0.75:
                    raise RuntimeError("La salida contiene silencio o saturación.")
            except Exception:
                path.unlink(missing_ok=True)
                raise
            progress(1,desc="Audio verificado")
            return str(path),f"Listo: {len(audio)/sr:.1f}s, {sr}Hz, RMS={rms:.3f}, XL Q8 + LM 4B Q8"
    except Exception as exc:
        raise gr.Error(f"Generación fallida: {type(exc).__name__}: {exc}") from exc


with gr.Blocks(title="ACE-Step 1.5 XL Q8 Music Studio") as app:
    gr.Markdown("# ACE-Step 1.5 XL Turbo — Music Studio Q8")
    gr.Markdown("Modelo XL real cuantizado a 8 bits y LM de 4B Q8. Generación local en Kaggle, sin API de pago.")
    with gr.Row():
        with gr.Column():
            style=gr.Textbox(label="Style / Estilo musical",lines=5,value="Melodic dubstep, complextro, aggressive growl bass, 150 BPM, chiptune arpeggios, futuristic synths, male Spanish vocals, crisp professional production")
            lyrics=gr.Textbox(label="Lyrics / Letra",lines=10,value="[Verse]\nLa noche brilla sin parar,\nlos circuitos vuelven a vibrar.\n[Chorus]\n¡Reinicia el mundo!\n¡Vamos a volar!")
            with gr.Row():
                seconds=gr.Slider(10,180,value=20,step=5,label="Duración segundos")
                bpm=gr.Slider(0,200,value=150,step=1,label="BPM (0=auto)")
            with gr.Row():
                seed=gr.Number(value=42,precision=0,label="Semilla")
                lang=gr.Dropdown(choices=["es","en","fr","pt","de"],value="es",label="Idioma")
            button=gr.Button("Generar canción",variant="primary")
        with gr.Column():
            audio=gr.Audio(label="Audio WAV",type="filepath")
            status=gr.Textbox(label="Estado",interactive=False)
    button.click(generate,[style,lyrics,seconds,bpm,seed,lang],[audio,status],concurrency_limit=1,concurrency_id="ace-q8")
    gr.Markdown("Servicio temporal. El motor genera desde la instancia Kaggle conectada.")
if __name__=="__main__":
    health=requests.get(API+"/health",timeout=10)
    health.raise_for_status()
    print("Engine health:",health.json(),flush=True)
    app.queue(default_concurrency_limit=1).launch(
        server_name="0.0.0.0",server_port=7868,share=True,
        allowed_paths=[str(OUT.resolve())],show_error=True)
