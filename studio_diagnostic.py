"""Experimental ACE-Step XL Q8 Studio to diagnose repeated loops."""
import json
import time
import uuid
import itertools
from pathlib import Path
import gradio as gr
import numpy as np
import soundfile as sf
import studio_gguf as core

BASE=Path(__file__).parent
OUT=BASE/"outputs"
OUT.mkdir(exist_ok=True)


def analyze_codes(codes):
    if isinstance(codes,list):
        tokens=[int(x) for x in codes]
    else:
        tokens=[int(s.strip()) for s in str(codes or "").split(",") if s.strip().isdigit()]
    if not tokens:
        return {"count":0,"unique":0,"longest_run":0,"unique_fraction":0,"loop_warning":False}
    max_run=max((len(list(g)) for _,g in itertools.groupby(tokens)), default=0)
    unique=len(set(tokens))
    frac=unique/len(tokens)
    # A run of 30 codes is ~6 seconds without changing FSQ code.
    # That's far beyond an ordinary 1- or 2-second sustained sound.
    severe=(len(tokens)>=50 and max_run>=30) or (len(tokens)>=100 and frac<0.08)
    warning=max_run>=12 or (len(tokens)>=100 and frac<0.3)
    return {
        "count":len(tokens),"unique":unique,"longest_run":max_run,
        "unique_fraction":round(frac,3),"loop_warning":warning,
        "severe_loop":severe,
    }


def make_song(style,lyrics,seconds,bpm,seed,lang,lm_enabled,lm_cfg,lm_temp,lm_top_p,
              progress=gr.Progress()):
    if not style.strip() or not lyrics.strip():
        raise gr.Error("Indica estilo y letra.")
    try:
        with core.LOCK:
            payload={
                "caption":style.strip(),"lyrics":lyrics.strip(),
                "duration":int(seconds),"bpm":int(bpm),"seed":int(seed),
                "vocal_language":lang,"synth_model":core.XL,
                "lm_model":core.LM,"output_format":"wav16",
                "use_cot_caption":False,
                "keyscale":"","timesignature":"4",
                "inference_steps":8,"guidance_scale":1.0,"shift":3.0,
                "lm_temperature":float(lm_temp),
                "lm_cfg_scale":float(lm_cfg),
                "lm_top_p":float(lm_top_p),
                "synth_batch_size":1,"task_type":"text2music",
            }
            stats=None
            if lm_enabled:
                progress(0,desc="LM Q8 · generando plan musical")
                plans=core.request_job("/lm",payload,progress).json()
                if not isinstance(plans,list) or not plans:
                    raise RuntimeError("El LM devolvió un plan vacío.")
                payload.update(plans[0])
                stats=analyze_codes(payload.get("audio_codes",""))
                if stats["severe_loop"]:
                    raise gr.Error(
                        "Detecté repetición anormal en el LM: "
                        f"{stats['longest_run']} códigos iguales seguidos; "
                        f"{stats['unique']} de {stats['count']} códigos son distintos. "
                        "Evité sintetizar audio probablemente repetitivo. "
                        "Cambia semilla/CFG/temperatura o prueba SIN LM."
                    )
            else:
                payload["audio_codes"]=""
            payload["synth_model"]=core.XL
            payload["output_format"]="wav16"
            progress(0.5,desc="XL Q8 · generando audio")
            response=core.request_job("/synth",payload,progress)
            raw=core.get_wav(response)
            path=OUT/("XL_Q8_DIAG_"+uuid.uuid4().hex[:10]+".wav")
            path.write_bytes(raw)
            try:
                a,sr=sf.read(path,always_2d=True)
                if not len(a) or not np.isfinite(a).all():
                    raise RuntimeError("WAV vacío o con NaN.")
                rms=float(np.sqrt(np.mean(a.astype("float64")**2)))
                clipping=float(np.mean(np.abs(a)>0.995))
                if rms<0.0005 or clipping>.75:
                    raise RuntimeError("WAV silencioso o saturado.")
            except Exception:
                path.unlink(missing_ok=True)
                raise
            metadata={
                "style":style,"lyrics":lyrics,"duration_requested":int(seconds),
                "duration_rendered":len(a)/sr,"bpm":bpm,"seed":seed,
                "LM_enabled":lm_enabled,"LM_CFG":lm_cfg,
                "LM_temp":lm_temp,"LM_top_p":lm_top_p,
                "code_analysis":stats,
            }
            path.with_suffix(".json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
            msg=(f"Audio válido: {len(a)/sr:.1f}s, {sr}Hz, RMS={rms:.3f}, "
                 f"semilla {'aleatoria' if int(seed)==-1 else int(seed)}.")
            if stats:
                msg+=(f"\nLM: {stats['count']} códigos, {stats['unique']} únicos, "
                      f"racha idéntica máxima {stats['longest_run']}.")
                if stats["loop_warning"]:
                    msg+="\nAviso: el LM tiene repeticiones; escucha el WAV para evaluar posibles loops."
            else:
                msg+="\nDiagnóstico: sin LM (XL directo desde texto)."
            return str(path),msg
    except gr.Error:
        raise
    except Exception as exc:
        raise gr.Error(f"{type(exc).__name__}: {exc}") from exc


with gr.Blocks(title="ACE-Step XL Q8 | Diagnóstico de loops") as demo:
    gr.Markdown("# ACE-Step XL Q8 · Prueba anti-loops")
    gr.Markdown(
        "Modelo **XL Q8** original. Prueba LM 4B con CFG más suave y semilla "
        "aleatoria, o desactiva el LM para aislar el origen del loop. "
        "Detecta patrones anormalmente repetidos en los códigos musicales."
    )
    with gr.Row():
        with gr.Column():
            style=gr.Textbox(
                label="Estilo / Style",lines=4,
                value=("Colombian orchestral salsa, 104 BPM, mature natural male Spanish singer, "
                       "rich trombone and trumpet section, syncopated piano montuno, "
                       "deep tumbao bass, congas, bongos, timbales, cowbell, warm studio recording"))
            lyrics=gr.Textbox(
                label="Letra / Lyrics",lines=9,
                value=("[Verse]\nCuando la salsa me llama,\nmi corazón vuelve a latir.\n"
                       "[Chorus]\nQue suenen los metales,\nque el piano hable por mí."))
            with gr.Row():
                duration=gr.Slider(10,180,value=60,step=5,label="Duración segundos")
                bpm=gr.Slider(0,200,value=104,step=1,label="BPM")
            with gr.Row():
                seed=gr.Number(value=-1,precision=0,label="Semilla (-1 = aleatoria)")
                lang=gr.Dropdown(["es","en","pt","fr","de"],value="es",label="Idioma")
            lm=gr.Checkbox(value=True,label="Usar LM de 4B para planificar la canción")
            with gr.Accordion("Control de repeticiones · LM",open=False):
                cfg=gr.Slider(1,3,value=1.4,step=.05,label="LM CFG (1 = menos rigidez)")
                temp=gr.Slider(.65,1.35,value=.95,step=.05,label="Temperatura LM (más = más variedad)")
                top_p=gr.Slider(.6,1,value=.95,step=.05,label="LM top-p")
            btn=gr.Button("Generar prueba",variant="primary")
        with gr.Column():
            audio=gr.Audio(label="Resultado WAV",type="filepath")
            status=gr.Textbox(label="Diagnóstico de códigos LM",lines=5,interactive=False)
    btn.click(make_song,[style,lyrics,duration,bpm,seed,lang,lm,cfg,temp,top_p],
              [audio,status],concurrency_id="music-gpu",concurrency_limit=1)
    gr.Markdown("Si un resultado se repite, prueba la misma canción sin LM. "
                "No se cambia ni descarga un modelo nuevo.")
if __name__=="__main__":
    print("ENGINE",core.requests.get(core.API+"/health",timeout=10).json(),flush=True)
    demo.queue(default_concurrency_limit=1).launch(
        server_name="0.0.0.0",server_port=7869,share=True,
        allowed_paths=[str(OUT.resolve())],show_error=True)
