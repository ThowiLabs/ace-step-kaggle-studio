"""ACE-Step 1.5 XL Q8: tabbed Gradio studio for audio-reference tasks.

Runs a separate GGUF/CUDA server (port 8087) for modes that require audio.
Original Smart Studio (port 7870) stays untouched on the first GPU.
"""
import json
import os
import subprocess
import uuid
from pathlib import Path
import time
import threading
import requests
import soundfile as sf
import numpy as np
import gradio as gr

import studio_smart
from studio_preview import preview_outputs

SERVER=os.environ.get("ACE_SERVER_URL", "http://127.0.0.1:8085")
SAVE=Path(__file__).parent/"studio_outputs"
SAVE.mkdir(parents=True,exist_ok=True)
XL="acestep-v15-xl-turbo-Q8_0.gguf"
BASE="acestep-v15-base-Q8_0.gguf"
EDIT_LOCK=threading.Lock()
MAX_SECONDS=600
MAX_UPLOAD_BYTES=150*1024*1024


def decode_source(path, limit_seconds=None):
    if not path:
        raise gr.Error("Sube una canción o un fragmento de audio WAV/MP3.")
    original=Path(path)
    if not original.is_file():
        raise gr.Error("El archivo de audio no está disponible.")
    if original.stat().st_size > MAX_UPLOAD_BYTES:
        raise gr.Error("El audio supera el límite de 150 MB. Comprímelo o recorta una sección.")
    converted=SAVE/("input_"+uuid.uuid4().hex[:10]+".wav")
    cmd=[
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i",str(original),"-vn","-map","0:a:0",
        "-ac","2","-ar","48000",
        "-c:a","pcm_s16le","-t",str(min(MAX_SECONDS, limit_seconds or MAX_SECONDS)),
        str(converted)
    ]
    try:
        task=subprocess.run(cmd,capture_output=True,text=True,timeout=150)
    except subprocess.TimeoutExpired:
        raise gr.Error("La conversión del audio excedió el tiempo permitido.")
    if task.returncode or not converted.exists():
        raise gr.Error("No pude preparar el audio. Utiliza WAV o MP3. "+task.stderr[-250:])
    seconds=sf.info(converted).duration
    if seconds<2.0:
        converted.unlink(missing_ok=True)
        raise gr.Error("Se necesitan al menos 2 segundos de audio.")
    if seconds>MAX_SECONDS:
        converted.unlink(missing_ok=True)
        raise gr.Error("Este modo admite audios de hasta 10 minutos.")
    return converted,seconds


def submit_multipart(payload,src,ref,progress):
    files={}
    opened=[]
    try:
        files["request"]=("params.json",json.dumps(payload,ensure_ascii=False).encode("utf-8"),"application/json")
        opened.append(src.open("rb"))
        files["audio"]=(src.name,opened[-1],"audio/wav")
        if ref:
            opened.append(ref.open("rb"))
            files["ref_audio"]=(ref.name,opened[-1],"audio/wav")
        response=requests.post(SERVER+"/synth",files=files,timeout=120)
        response.raise_for_status()
        job=response.json().get("id")
        if not job:
            raise gr.Error(f"El servidor no devolvió un trabajo: {response.text[:160]}")
    finally:
        for f in opened:f.close()
    start=time.monotonic()
    while True:
        state=requests.get(SERVER+"/job",params={"id":job},timeout=30)
        state.raise_for_status()
        status=state.json().get("status")
        if status=="done":break
        if status in ("failed","cancelled"):
            raise gr.Error(
                f"La síntesis falló en el modo {payload['task_type']}. "
                "Prueba una pista más corta, otro estilo o desactiva el audio de timbre."
            )
        if time.monotonic()-start>1800:
            raise gr.Error("La generación superó 30 minutos. Prueba un fragmento más corto.")
        progress(0.5,desc=f"{payload['task_type']} · {status} · {int(time.monotonic()-start)}s")
        time.sleep(3)
    done=requests.get(SERVER+"/job",params={"id":job,"result":1},timeout=180)
    done.raise_for_status()
    from studio_gguf import get_wav
    return get_wav(done)


def audio_valid(raw,payload):
    p=SAVE/(payload["task_type"].replace("-","_")+"_"+uuid.uuid4().hex[:9]+".wav")
    p.write_bytes(raw)
    try:
        x,sr=sf.read(p,always_2d=True)
        if not len(x) or not np.isfinite(x).all():
            raise ValueError("WAV sin muestras válidas.")
        rms=float(np.sqrt(np.mean(x.astype(np.float64)**2)))
        clipping=float(np.mean(np.abs(x)>.995))
        if rms<0.0004 or clipping>=.8:
            raise ValueError("El WAV generado está silencioso o saturado.")
        info={"mode":payload["task_type"],"requested_style":payload["caption"],
              "actual_seconds":round(len(x)/sr,2),"sample_rate":sr,
              "rms":round(rms,4),"clipping_fraction":round(clipping,5)}
        p.with_suffix(".json").write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding="utf8")
        return str(p),f"Listo · {len(x)/sr:.1f} s · {sr} Hz · {payload['task_type']} · WAV válido"
    except Exception as e:
        p.unlink(missing_ok=True)
        raise gr.Error(f"La salida musical no pasó la validación: {e}")


def run_mode(mode,src_audio,style,lyrics,strength=0.5,start=0,end=10,track="guitar",
             separate_ref=None,preview_seconds=None,method_note="",progress=gr.Progress()):
    if not (style or "").strip() and mode not in ("extract",):
        raise gr.Error("Escribe cómo quieres que suene el resultado.")
    with EDIT_LOCK:
        converted,seconds=decode_source(src_audio,limit_seconds=preview_seconds)
        ref_path=None
        if separate_ref:
            ref_path,_=decode_source(separate_ref,limit_seconds=preview_seconds)
        elif mode=="cover-nofsq":
            ref_path=converted  # Official recommendation for faithful remix
        if mode=="repaint":
            if end<=start:
                raise gr.Error("El segundo final debe ser mayor que el inicial.")
            if start>=seconds:
                raise gr.Error(f"La zona empieza después del final del audio ({seconds:.1f}s).")
            if end > MAX_SECONDS:
                raise gr.Error("El resultado no puede superar los 600 segundos.")
        model = BASE if mode in ("lego","extract","complete") else XL
        payload={
            "task_type":mode,
            "synth_model":model,
            "caption":style.strip() or "Instrumental",
            "lyrics":lyrics.strip() if lyrics else "[Instrumental]",
            "duration":round(seconds,3),
            "seed":-1,
            "output_format":"wav16",
            "inference_steps":50 if model==BASE else 8,
            "guidance_scale":1.0,
            "shift":1.0 if model==BASE else 3.0,
            "audio_cover_strength":float(strength),
            "lm_model":"acestep-5Hz-lm-4B-Q8_0.gguf",
        }
        if mode=="repaint":
            payload.update(repainting_start=float(start),repainting_end=float(end))
        if mode in ("lego","extract","complete"):
            payload["track"]=track
        try:
            progress(0.05,desc=f"Preparando audio de {seconds:.1f} segundos")
            result=submit_multipart(payload,converted,ref_path,progress)
            file,message=audio_valid(result,payload)
            if method_note:
                message += "\n"+method_note
            if lyrics.strip().lower()=="[instrumental]" or not lyrics.strip():
                if mode in ("cover","cover-nofsq"):
                    message += "\nVoz: se pidió instrumental; para conservar voz, introduce una letra."
            progress(.98,desc="Preparando vista previa MP3 comprimida...")
            compressed=preview_outputs(file,message)
            progress(1,desc="Vista previa MP3 lista; WAV original disponible")
            return compressed
        finally:
            converted.unlink(missing_ok=True)
            if ref_path is not None and ref_path!=converted:
                ref_path.unlink(missing_ok=True)


COVER_PREVIEW="Prueba de 45 segundos (recomendada)"
COVER_STABLE="Canción completa (más estable)"
COVER_EXPERIMENTAL="Cover original FSQ (experimental)"

def choose_cover_recipe(strategy,strength):
    """Choose a conservative algorithm; never silently truncate whole songs."""
    strength=float(strength)
    if strategy==COVER_PREVIEW:
        return "cover",min(0.95,max(0.65,strength)),45,(
            "Prueba corta de 45 segundos; sube de nuevo el archivo para generar "
            "la canción completa si te convence el estilo."
        )
    if strategy==COVER_STABLE:
        # Pure audio-latent reference, avoids the lossy FSQ roundtrip.
        return "cover-nofsq",min(0.45,max(0.25,strength*0.5)),None,(
            "Estabilidad: remix sin FSQ. Conserva más estructura de la canción original "
            "y puede transformar el género con menor intensidad."
        )
    if strategy==COVER_EXPERIMENTAL:
        return "cover",strength,None,(
            "Modo creativo FSQ original: experimental en canciones largas; "
            "puede producir patrones repetitivos."
        )
    raise ValueError("Estrategia de cover desconocida: "+str(strategy))

def cover_creative(audio,style,lyrics,strength,ref,strategy,progress=gr.Progress()):
    mode,actual_strength,preview,note=choose_cover_recipe(strategy,strength)
    return run_mode(
        mode,audio,style,lyrics,strength=actual_strength,
        separate_ref=ref,preview_seconds=preview,method_note=note,
        progress=progress
    )

def cover_faithful(audio,style,lyrics,strength,ref,progress=gr.Progress()):
    return run_mode("cover-nofsq",audio,style,lyrics,strength=strength,separate_ref=ref,progress=progress)

def repaint(audio,style,lyrics,start,end,progress=gr.Progress()):
    return run_mode("repaint",audio,style,lyrics,start=start,end=end,progress=progress)

def add_track(audio,style,track,progress=gr.Progress()):
    return run_mode("lego",audio,style,"[Instrumental]",track=track,progress=progress)

def extract_track(audio,track,progress=gr.Progress()):
    return run_mode("extract",audio,"", "[Instrumental]",track=track,progress=progress)

def complete_track(audio,style,track,progress=gr.Progress()):
    return run_mode("complete",audio,style,"[Instrumental]",track=track,progress=progress)


def create_song_preview(style,lyrics,bpm,language,tries,rescue,progress=gr.Progress()):
    wav,message=studio_smart.make(
        style,lyrics,bpm,language,tries,rescue,progress=progress
    )
    progress(.98,desc="Comprimiendo preview MP3; conservando WAV original...")
    result=preview_outputs(wav,message)
    progress(1,desc="Preview MP3 lista")
    return result


def output_pair():
    return (
        gr.Audio(label="Vista previa comprimida · MP3 128 kbps",type="filepath",format="mp3"),
        gr.File(label="Descargar WAV original sin pérdida",type="filepath"),
        gr.Textbox(label="Resultado y tamaño del audio",lines=4,interactive=False),
    )

def bind(button,callback,inputs,outputs):
    button.click(callback,inputs,outputs,
                 concurrency_id="shared-GGUF-edits",concurrency_limit=1)


with gr.Blocks(title="ACE-Step XL Q8 | Studio multipestaña") as app:
    gr.Markdown("# 🎶 ACE-Step 1.5 · Music Studio")
    gr.Markdown("**En todos los modos:** escucha una **vista previa MP3 comprimida (128 kbps)** y, si quieres calidad original, descarga el **WAV completo** por separado. La compresión no altera el audio generado por la IA.")
    gr.Markdown(
        "Generación con **XL Turbo Q8**, edición con **audio de referencia**, "
        "y herramientas de pistas con **Base Q8**. Cada modo usa su propia pestaña. "
        "El Gradio original continúa activo por separado."
    )
    with gr.Tabs():
        with gr.Tab("🎵 Crear canción"):
            gr.Markdown(
                "Este modo conserva **autoduración, hasta 3 reintentos automáticos y "
                "protección anti-loops**. La IA decide cuánto debe durar según la letra."
            )
            with gr.Row():
                with gr.Column():
                    s1=gr.Textbox(label="Style",lines=5,value="Classic Colombian orchestral salsa, powerful brass, piano montuno, tumbao bass, congas, trombones, male Spanish singer, professional recording")
                    l1=gr.Textbox(label="Lyrics",lines=9,value="[Verse]\nLa vida cambia cuando vuelves a bailar.\n[Chorus]\nQue suenen los metales, la noche va a empezar.")
                    with gr.Row():
                        bpm=gr.Slider(0,200,value=0,step=1,label="BPM (0 = IA)")
                        language=gr.Dropdown(["es","en","pt","fr","de"],value="es",label="Idioma")
                    tries=gr.Slider(1,4,step=1,value=3,label="Intentos anti-loop")
                    rescue=gr.Checkbox(value=True,label="Rescatar con XL directo si colapsa el LM")
                    b1=gr.Button("Crear canción",variant="primary")
                with gr.Column():
                    a1,w1,t1=output_pair()
            b1.click(create_song_preview,[s1,l1,bpm,language,tries,rescue],[a1,w1,t1],
                     concurrency_id="original-Music-studio",concurrency_limit=1)

        with gr.Tab("🎨 Cover creativo"):
            gr.Markdown(
                "**Transforma una canción a otro género**. Preserva algunas ideas de la "
                "referencia, pero puede cambiar melodía, ritmo y arreglos. Usa XL Q8."
            )
            with gr.Row():
                with gr.Column():
                    c_audio=gr.Audio(label="Canción original WAV o MP3",type="filepath",sources=["upload"])
                    c_style=gr.Textbox(label="Nuevo estilo",lines=4,value="Colombian orchestral salsa, powerful brass, piano montuno, tumbao bass, natural Spanish male singer, live congas")
                    c_lyrics=gr.Textbox(label="Letra en español (vacío = instrumental)",lines=5,value="")
                    gr.Markdown("**Para generar voz:** pega una letra con `[Verse]` y `[Chorus]`. Si no escribes ninguna, se indica al modelo que haga música instrumental.")
                    c_strategy=gr.Radio(
                        choices=[COVER_PREVIEW,COVER_STABLE,COVER_EXPERIMENTAL],
                        value=COVER_PREVIEW,label="Cómo generar el cover",
                        info="Primero prueba 45 s. Para una canción larga, elige el método sin FSQ."
                    )
                    c_str=gr.Slider(0,1,value=.70,step=.05,label="Influencia de la canción original")
                    c_ref=gr.Audio(label="Referencia adicional de timbre (opcional)",type="filepath",sources=["upload"])
                    c_b=gr.Button("Crear cover",variant="primary")
                with gr.Column():
                    c_out,c_wav,c_msg=output_pair()
            bind(c_b,cover_creative,[c_audio,c_style,c_lyrics,c_str,c_ref,c_strategy],[c_out,c_wav,c_msg])

        with gr.Tab("🎚️ Remix fiel"):
            gr.Markdown(
                "**Cover sin FSQ**: utiliza los detalles originales de audio para conservar "
                "mejor la melodía, estructura y timbre. Usa XL Q8."
            )
            with gr.Row():
                with gr.Column():
                    f_audio=gr.Audio(label="Audio original",type="filepath",sources=["upload"])
                    f_style=gr.Textbox(label="Cómo reinterpretarlo",lines=4,value="Polished studio production, rich orchestral brass, crisp drums, warm vocal, clear balanced mix")
                    f_lyrics=gr.Textbox(label="Letra o [Instrumental]",lines=5,value="[Instrumental]")
                    f_str=gr.Slider(0,1,value=.35,step=.05,label="Fuerza de contexto de audio",info="Prueba entre 0.2 y 0.5 según la documentación")
                    f_ref=gr.Audio(label="Referencia de timbre distinta (opcional; si no, se usa el original)",type="filepath",sources=["upload"])
                    f_b=gr.Button("Crear remix",variant="primary")
                with gr.Column():
                    f_out,f_wav,f_msg=output_pair()
            bind(f_b,cover_faithful,[f_audio,f_style,f_lyrics,f_str,f_ref],[f_out,f_wav,f_msg])

        with gr.Tab("✂️ Editar fragmento"):
            gr.Markdown(
                "**Repaint**: genera una zona nueva y conserva el resto del audio. "
                "Introduce los segundos de inicio y fin de la región."
            )
            with gr.Row():
                with gr.Column():
                    p_audio=gr.Audio(label="Audio que quieres editar",type="filepath",sources=["upload"])
                    p_style=gr.Textbox(label="Estilo deseado de la nueva parte",lines=4,value="Trombone solo with piano montuno and warm orchestral salsa percussion")
                    p_lyrics=gr.Textbox(label="Letra de la sección o [Instrumental]",lines=4,value="[Instrumental]")
                    with gr.Row():
                        p_start=gr.Number(value=3,label="Desde segundo",precision=1)
                        p_end=gr.Number(value=7,label="Hasta segundo",precision=1)
                    p_b=gr.Button("Regenerar fragmento",variant="primary")
                with gr.Column():
                    p_out,p_wav,p_msg=output_pair()
            bind(p_b,repaint,[p_audio,p_style,p_lyrics,p_start,p_end],[p_out,p_wav,p_msg])

        with gr.Tab("➕ Añadir instrumento"):
            gr.Markdown(
                "**LEGO**: crea un instrumento sobre una pista existente. "
                "Este modo requiere **Base Q8**, no XL Turbo. "
                "El resultado puede ser una pista aislada y no una mezcla completa."
            )
            with gr.Row():
                with gr.Column():
                    lego_audio=gr.Audio(label="Pista de acompañamiento",type="filepath",sources=["upload"])
                    lego_style=gr.Textbox(label="Instrucciones del nuevo instrumento",value="Expressive bright trumpet melody complementing Colombian salsa montuno",lines=4)
                    lego_track=gr.Dropdown(["brass","guitar","keyboard","percussion","bass","drums","strings","synth","woodwinds","vocals"],value="brass",label="Instrumento")
                    lego_b=gr.Button("Generar instrumento",variant="primary")
                with gr.Column():
                    lego_out,lego_wav,lego_msg=output_pair()
            bind(lego_b,add_track,[lego_audio,lego_style,lego_track],[lego_out,lego_wav,lego_msg])

        with gr.Tab("🎛️ Extraer instrumento"):
            gr.Markdown(
                "**Extract**: intenta aislar voces, batería, bajo u otra familia instrumental. "
                "Requiere **Base Q8**. No garantiza separación perfecta de stems."
            )
            with gr.Row():
                with gr.Column():
                    x_audio=gr.Audio(label="Canción a separar",type="filepath",sources=["upload"])
                    x_track=gr.Dropdown(["vocals","backing_vocals","drums","bass","guitar","keyboard","percussion","strings","synth","fx","brass","woodwinds"],value="vocals",label="Qué extraer")
                    x_b=gr.Button("Extraer pista",variant="primary")
                with gr.Column():
                    x_out,x_wav,x_msg=output_pair()
            bind(x_b,extract_track,[x_audio,x_track],[x_out,x_wav,x_msg])

        with gr.Tab("🧩 Completar acompañamiento"):
            gr.Markdown(
                "**Complete**: sube una pista aislada (por ejemplo, voz sola) y genera "
                "un acompañamiento. Requiere **Base Q8**. La duración seguirá el archivo."
            )
            with gr.Row():
                with gr.Column():
                    full_audio=gr.Audio(label="Voz o instrumento aislado",type="filepath",sources=["upload"])
                    full_style=gr.Textbox(label="Descripción del acompañamiento",lines=4,value="Colombian salsa orchestra with piano montuno, tumbao bass, strong horns, congas and timbales")
                    full_track=gr.Dropdown(["drums","brass","bass","guitar","keyboard","percussion","strings","synth"],value="drums",label="Instrumento que quieres agregar al audio")
                    full_b=gr.Button("Completar canción",variant="primary")
                with gr.Column():
                    full_out,full_wav,full_msg=output_pair()
            bind(full_b,complete_track,[full_audio,full_style,full_track],[full_out,full_wav,full_msg])

    gr.Markdown(
        "**Archivos:** WAV y MP3 recomendados, máximo 150 MB, hasta 10 minutos de duración. "
        "Para mejores resultados empieza con fragmentos de 10–30 segundos. "
        "Usa grabaciones propias o para las que tengas autorización."
    )

if __name__=="__main__":
    health=requests.get(SERVER+"/health",timeout=10)
    health.raise_for_status()
    print("EDIT_SERVER",health.json(),flush=True)
    app.queue(default_concurrency_limit=1).launch(
        server_name="0.0.0.0",server_port=int(os.environ.get("GRADIO_PORT","7860")),share=True,
        allowed_paths=[str(SAVE.resolve()),str((Path(__file__).parent/"outputs").resolve())],
        show_error=True
    )
