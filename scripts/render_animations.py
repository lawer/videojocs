#!/usr/bin/env python3
"""
Pre-renderitzador d'animacions MakeCode Arcade per a Jekyll.
Llegeix fitxers TypeScript de _demos/*.ts, compila i executa el simulador
headless per gravar els fotogrames i generar fitxers .gif ultra-optimitzats
a assets/images/animations/<nom>.gif.

Seguretat anticòpia: El directori _demos/ és ignorat per Jekyll i mai es publica
a la web. L'alumnat només rep el fitxer GIF estàtic (píxels purs).

Ús:
    python3 scripts/render_animations.py           # Renderitza animacions noves o modificades
    python3 scripts/render_animations.py --check   # Comprova si totes les animacions estan al dia (retorna 0 o 1)
    python3 scripts/render_animations.py --clean   # Elimina animacions òrfenes
    python3 scripts/render_animations.py --force   # Força la regeneració de totes les animacions
"""

import sys
import os
import re
import io
import json
import time
import base64
import hashlib
import argparse
from pathlib import Path
import requests
from PIL import Image

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = WORKSPACE_ROOT / "_demos"
OUTPUT_DIR = WORKSPACE_ROOT / "assets" / "images" / "animations"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"


def parse_demo_file(ts_path: Path):
    """
    Llegeix el fitxer .ts i extreu els metadats de configuració i el codi.
    """
    raw_content = ts_path.read_text(encoding="utf-8")
    lines = raw_content.splitlines()

    duration = 3.0
    fps = 15
    scale = 2
    keys = []

    for l in lines:
        m_dur = re.match(r"^\s*//\s*duration:\s*([0-9.]+)", l, re.I)
        if m_dur:
            duration = float(m_dur.group(1))

        m_fps = re.match(r"^\s*//\s*fps:\s*([0-9]+)", l, re.I)
        if m_fps:
            fps = int(m_fps.group(1))

        m_scale = re.match(r"^\s*//\s*scale:\s*([0-9]+)", l, re.I)
        if m_scale:
            scale = int(m_scale.group(1))

        m_keys = re.match(r"^\s*//\s*keys:\s*(.+)", l, re.I)
        if m_keys:
            keys = [k.strip().lower() for k in m_keys.group(1).split(",")]

    content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()[:16]

    return {
        "name": ts_path.stem,
        "path": ts_path,
        "code": raw_content,
        "hash": content_hash,
        "duration": duration,
        "fps": fps,
        "scale": scale,
        "keys": keys,
    }


def find_all_demos():
    """
    Troba tots els fitxers .ts dins de _demos/.
    """
    if not DEMOS_DIR.exists():
        return []

    demos = []
    for p in sorted(DEMOS_DIR.glob("*.ts")):
        demos.append(parse_demo_file(p))
    return demos


def load_manifest():
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_manifest(data):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def upload_project(name: str, code: str):
    """
    Puja el projecte a l'API de MakeCode Arcade per obtenir un ID d'execució.
    """
    pxt_json = {
        "name": name,
        "dependencies": {
            "device": "*"
        },
        "description": "",
        "files": [
            "main.ts"
        ],
        "targetVersions": {
            "target": "2.0.0"
        }
    }

    payload = {
        "name": name,
        "target": "arcade",
        "text": {
            "main.ts": code,
            "pxt.json": json.dumps(pxt_json)
        }
    }

    r = requests.post("https://www.makecode.com/api/scripts", json=payload, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Error pujant el projecte a MakeCode ({r.status_code}): {r.text}")

    data = r.json()
    shortid = data.get("shortid") or data.get("id")
    return shortid


def render_animation_headless(demo: dict, driver):
    """
    Executa el simulador de MakeCode en Chrome headless i captura els fotogrames.
    """
    from PIL import Image

    print(f"-> Pujant projecte '{demo['name']}' a MakeCode...", end="", flush=True)
    shortid = upload_project(demo["name"], demo["code"])
    print(f" ID: {shortid}")

    run_url = f"https://arcade.makecode.com/--run?id={shortid}"
    print(f"-> Carregant simulador a {run_url}...", end="", flush=True)
    driver.get(run_url)

    # Esperar a que l'iframe del simulador aparegui
    canvas = None
    for _ in range(20):
        time.sleep(0.5)
        iframes = driver.find_elements("css selector", "iframe")
        if iframes:
            driver.switch_to.frame(iframes[0])
            canvases = driver.find_elements("css selector", "canvas")
            if canvases:
                canvas = canvases[0]
                break
            driver.switch_to.default_content()

    if not canvas:
        raise RuntimeError("No s'ha pogut trobar el canvas del simulador de MakeCode.")

    print(" Simulador llest!")

    # Simular tecles si estan definides
    if demo["keys"]:
        key_map = {
            "right": ("ArrowRight", 39),
            "left": ("ArrowLeft", 37),
            "up": ("ArrowUp", 38),
            "down": ("ArrowDown", 40),
            "a": ("KeyZ", 90),
            "b": ("KeyX", 88),
            "space": ("Space", 32),
        }
        for k in demo["keys"]:
            if k in key_map:
                key_code, key_num = key_map[k]
                driver.execute_script(f"""
                window.dispatchEvent(new KeyboardEvent('keydown', {{ key: '{key_code}', code: '{key_code}', keyCode: {key_num}, bubbles: true }}));
                """)

    fps = max(5, min(30, demo["fps"]))
    interval = 1.0 / fps
    total_frames = int(demo["duration"] * fps)
    scale = max(1, min(4, demo["scale"]))
    target_w = 160 * scale
    target_h = 120 * scale

    frames = []
    print(f"-> Gravant {total_frames} fotogrames a {fps} FPS ({demo['duration']}s)...", end="", flush=True)
    for _ in range(total_frames):
        time.sleep(interval)
        data_url = driver.execute_script("return arguments[0].toDataURL('image/png');", canvas)
        if "data:image/png;base64," in data_url:
            raw_b64 = data_url.split("data:image/png;base64,")[1]
            png_bytes = base64.b64decode(raw_b64)
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            scaled = img.resize((target_w, target_h), Image.NEAREST)
            frames.append(scaled)

    print(f" {len(frames)} fotogrames capturats.")

    if not frames:
        raise RuntimeError("No s'ha capturat cap fotograma vàlid.")

    out_file = OUTPUT_DIR / f"{demo['name']}.gif"
    duration_ms = int(1000 / fps)

    # Convertir a paleta per optimitzar la mida del GIF
    paletted_frames = []
    for f in frames:
        # Quantize preservant colors pixel art
        paletted_frames.append(f.convert("RGB").quantize(colors=64))

    paletted_frames[0].save(
        out_file,
        save_all=True,
        append_images=paletted_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )

    size_kb = out_file.stat().st_size // 1024
    print(f"-> Animació guardada amb èxit: {out_file.relative_to(WORKSPACE_ROOT)} ({size_kb} KB)")


def main():
    parser = argparse.ArgumentParser(description="Pre-renderitzador d'animacions MakeCode Arcade")
    parser.add_argument("--check", action="store_true", help="Comprova si totes les animacions estan al dia")
    parser.add_argument("--clean", action="store_true", help="Elimina fitxers GIF que ja no tenen fitxer .ts a _demos/")
    parser.add_argument("--force", action="store_true", help="Força la regeneració de totes les animacions")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    demos = find_all_demos()
    manifest = load_manifest()

    active_names = {d["name"] for d in demos}
    existing_gifs = {p.stem for p in OUTPUT_DIR.glob("*.gif")}

    print(f"Total de demostracions trobades a _demos/: {len(demos)}")

    if args.clean:
        orphans = existing_gifs - active_names
        if orphans:
            print(f"Eliminant {len(orphans)} animacions òrfenes...")
            for oph in orphans:
                (OUTPUT_DIR / f"{oph}.gif").unlink(missing_ok=True)
                manifest.pop(oph, None)
            save_manifest(manifest)
        else:
            print("No hi ha animacions òrfenes per netejar.")

    missing = []
    for d in demos:
        name = d["name"]
        gif_file = OUTPUT_DIR / f"{name}.gif"
        if not gif_file.exists() or manifest.get(name, {}).get("hash") != d["hash"] or args.force:
            missing.append(d)

    if args.check:
        if missing:
            print(f"[ALERTA] Falten {len(missing)} animacions per renderitzar:")
            for m in missing:
                print(f"  - {m['name']} (_demos/{m['name']}.ts)")
            print("\nExecuta 'python3 scripts/render_animations.py' per generar-les.")
            sys.exit(1)
        else:
            print("[OK] Totes les animacions estan pre-renderitzades i al dia.")
            sys.exit(0)

    if not missing:
        print("[OK] Totes les animacions estan al dia. No cal renderitzar res.")
        sys.exit(0)

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    print(f"-> Inicialitzant Chrome headless per renderitzar {len(missing)} animacions...")
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=opts)

    try:
        for demo in missing:
            print(f"\n--- Processant {demo['name']} ---")
            render_animation_headless(demo, driver)
            manifest[demo["name"]] = {
                "hash": demo["hash"],
                "duration": demo["duration"],
                "fps": demo["fps"],
                "scale": demo["scale"],
                "updated": int(time.time()),
            }
            save_manifest(manifest)
    finally:
        driver.quit()

    print("\n-> Procés de renderitzat d'animacions finalitzat amb èxit!")


if __name__ == "__main__":
    main()
