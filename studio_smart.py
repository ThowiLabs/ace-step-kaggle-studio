"""XL Q8 Studio: LM retry, non-degenerate code validation, auto duration."""
import json
import secrets
import uuid
from pathlib import Path

import gradio as gr
import numpy as np
import soundfile as sf

import studio_gguf as engine
from studio_diagnostic import analyze_codes

OUT=Path(__file__).parent/"outputs"
OUT.mkdir(exist_ok=True)
CFG_PRESETS=[
    (1.0,0.92,0.96),
    (1.0,1.08,0.99),
    (1.2,1.0,0.98),
    (1.0,0.85,0.90),
]

def check_codes(raw):
    stats=analyze_codes(raw)
    codes=[int(x) for x in str(raw or "").split(",") if x.strip().isdigit()]
    n=stats["count"]
    run=stats["longest_run"]
    ratio=stats["unique_fraction"]
    # Besides single-token collapse, detect multi-token oscillation
    # (e.g. A,B,A,B repeating for 950 of 1000 tokens).
    tail=codes[max(0,n//4):]
    period_scores={}
    if len(tail)>=60:
        for period in range(1,9):
            score=sum(tail[i]==tail[i-period] for i in range(period,len(tail)))
            period_scores[period]=round(score/(len(tail)-period),4)
    worst_period=max(period_scores,key=period_scores.get) if period_scores else 0
    worst_score=period_scores.get(worst_period,0)
    stats["loop_period"]=worst_period
    stats["period_match"]=worst_score
    stats["degenerate"]=(
        n==0 or
        (n>=25 and run>=20) or
        (n>=70 and ratio<0.15) or
        (n>=70 and run/n>=0.45) or
        (n>=100 and worst_score>=0.90)
    )
    return stats

def make(style,lyrics,bpm,language,tries,rescue,progress=gr.Progress()):
    if not str(style or "").strip() or not str(lyrics or "").strip():
        raise gr.Error("Escribe una descripción musical y la letra.")
    trials=[]
    best=None
    initial=None
    max_tries=max(1,min(4,int(tries)))
    request={
        "caption":style.strip(),
        "lyrics":lyrics.strip(),
        "duration":0,  # Model chooses. Zero is the GGUF unset sentinel.
        "bpm":int(bpm),
        "keyscale":"",
        "timesignature":"",
        "vocal_language":language,
        "synth_model":engine.XL,
        "lm_model":engine.LM,
        "task_type":"text2music",
        "lm_batch_size":1,
        "synth_batch_size":1,
        "use_cot_caption":False,
        "inference_steps":8,
        "guidance_scale":1.0,
        "shift":3.0,
        "dcw_scaler":0.0,
        "dcw_high_scaler":0.0,
        "output_format":"wav16",
    }
    with engine.LOCK:
        for idx in range(max_tries):
            cfg,temp,top_p=CFG_PRESETS[idx]
            sd=secrets.randbelow(2**32)
            lmsd=secrets.randbelow(2**32)
            payload=request | {
                "seed":sd,"lm_seed":lmsd,
                "lm_cfg_scale":cfg,
                "lm_temperature":temp,
                "lm_top_p":top_p,
                "lm_top_k":0,
            }
            progress(idx/max_tries*.7,desc=f"Composición IA intento {idx+1}/{max_tries}")
            try:
                plans=engine.request_job("/lm",payload,progress).json()
                if not isinstance(plans,list) or not plans:
                    raise RuntimeError("LM no devolvió una composición.")
                plan=plans[0]
                if initial is None:
                    initial=plan.copy()
                codecheck=check_codes(plan.get("audio_codes",""))
                report={
                    "attempt":idx+1,"lm_seed":lmsd,"synth_seed":sd,
                    "lm_cfg":cfg,"lm_temperature":temp,"lm_top_p":top_p,
                    "chosen_duration":plan.get("duration"),
                } | codecheck
                trials.append(report)
                print("AUTO_LM",json.dumps(report,ensure_ascii=False),flush=True)
                if not codecheck["degenerate"]:
                    best=plan.copy()
                    best["seed"]=sd
                    best["lm_seed"]=lmsd
                    break
            except gr.Error:
                raise
            except Exception as exc:
                trials.append({"attempt":idx+1,"error":str(exc)})
                print("LM_ATTEMPT_FAILED",str(exc),flush=True)
        mode="Planificador LM"
        if best is None:
            if not rescue:
                raise gr.Error(
                    "El LM cayó en repetición tras todos los intentos. "
                    + ", ".join(
                        f"#{x['attempt']}: racha {x.get('longest_run','error')}"
                        for x in trials
                    )
                )
            if initial is None:
                raise gr.Error("Ningún LM pudo elegir la duración automática.")
            best=initial.copy()
            best["audio_codes"]=""
            best["seed"]=secrets.randbelow(2**32)
            mode="XL directo: rescate sin códigos repetitivos"
        duration=float(best.get("duration",0) or 0)
        if not (10<=duration<=600):
            raise gr.Error(
                f"El modelo eligió {duration} segundos. El rango técnico "
                "es 10-600 segundos. Prueba otra generación."
            )
        best.update(
            caption=style.strip(),
            lyrics=lyrics.strip(),
            synth_model=engine.XL,
            output_format="wav16",
            inference_steps=8,
            guidance_scale=1.,
            shift=3.,
            dcw_scaler=0.,
            dcw_high_scaler=0.,
        )
        progress(.8,desc=f"Sintetizando {mode}, duración IA {duration:.0f}s")
        result=engine.request_job("/synth",best,progress)
        raw=engine.get_wav(result)
        target=OUT/("XL_AUTO_"+uuid.uuid4().hex[:9]+".wav")
        target.write_bytes(raw)
        try:
            wav,sr=sf.read(target,always_2d=True)
            if len(wav)<sr or not np.isfinite(wav).all():
                raise RuntimeError("Audio vacío o inválido.")
            rms=float(np.sqrt(np.mean(wav.astype(np.float64)**2)))
            clipped=float(np.mean(np.abs(wav)>.995))
            if rms<.0005 or clipped>.75:
                raise RuntimeError("Audio silencioso o saturado.")
        except Exception:
            target.unlink(missing_ok=True)
            raise
        actual=len(wav)/sr
        diagnosis={
            "style":style,"lyrics":lyrics,"requested_duration":None,
            "AI_duration":duration,"actual_seconds":round(actual,2),
            "synthesis_mode":mode,"lm_attempts":trials,
            "XL_model":engine.XL,"LM_model":engine.LM,
            "seed":best.get("seed"),
        }
        target.with_suffix(".json").write_text(
            json.dumps(diagnosis,ensure_ascii=False,indent=2),encoding="utf-8"
        )
        summary=(
            f"Audio OK: {actual:.1f}s a {sr}Hz; IA eligió {duration:.0f}s.\n"
            f"{mode}. Intentos LM: {len(trials)}.\n"
            + " | ".join(
                f"#{x['attempt']} racha {x.get('longest_run','error')}"
                for x in trials
            )
        )
        if mode!="Planificador LM":
            summary+="\nEl audio se rescató sin los códigos repetitivos."
        progress(1,desc="WAV generado")
        return str(target),summary

with gr.Blocks(title="ACE-Step XL Q8 - Auto-duración Anti-Loops") as app:
    gr.Markdown("# ACE-Step XL Q8 · Canciones inteligentes")
    gr.Markdown(
        "Duración elegida por la IA según tu Style y Lyrics. "
        "Sin selector artificial de 180 segundos. "
        "Límite del modelo: 10 a 600 segundos. "
        "Corrección automática de planes LM degenerados."
    )
    with gr.Row():
        with gr.Column():
            style=gr.Textbox(
                label="Style / Música",lines=5,
                value=("Colombian orchestral salsa, syncopated piano montuno, "
                       "tumbao bass, prominent brass section, trumpets, trombones, "
                       "congas, timbales, male Spanish vocalist, elegant salsa orchestra")
            )
            lyrics=gr.Textbox(
                label="Lyrics / Letra",lines=10,
                value=("[Verse]\nCuando la salsa me llama,\nse enciende mi corazón.\n"
                       "[Chorus]\nQue suenen los metales,\nque baile mi canción.")
            )
            with gr.Row():
                bpm=gr.Slider(0,200,value=0,step=1,label="BPM · 0 = IA elige")
                lang=gr.Dropdown(["es","en","pt","fr","de"],value="es",label="Idioma")
            with gr.Accordion("Protección contra loops",open=True):
                tries=gr.Slider(1,4,value=3,step=1,label="Máximo de intentos automáticos LM")
                rescue=gr.Checkbox(value=True,label="Rescatar directamente con XL si el LM vuelve a fallar")
            start=gr.Button("Generar canción",variant="primary")
        with gr.Column():
            audio=gr.Audio(label="Canción WAV",type="filepath")
            status=gr.Textbox(label="Informe de generación y loops",lines=6,interactive=False)
    start.click(make,[style,lyrics,bpm,lang,tries,rescue],[audio,status],
                concurrency_id="music-auto",concurrency_limit=1)
if __name__=="__main__":
    print("SERVER HEALTH",engine.requests.get(engine.API+"/health",timeout=10).json(),flush=True)
    app.queue(default_concurrency_limit=1).launch(
        server_name="0.0.0.0",server_port=7870,share=True,
        allowed_paths=[str(OUT.resolve())],show_error=True
    )
