#!/usr/bin/env python3
"""
Pre-renderitzador natiu de blocs MakeCode Arcade per a Jekyll.
Escaneja els fitxers Markdown en cerca de blocs ```blocks ... ```,
calcula el seu hash determinista SHA-256 i renderitza les imatges PNG
estàtiques a assets/images/blocks/<hash>.png usant Chrome headless i MakeCode.

Ús:
    python3 scripts/render_blocks.py           # Renderitza els blocs que falten
    python3 scripts/render_blocks.py --check   # Comprova si tots els blocs estan al dia (retorna 0 o 1)
    python3 scripts/render_blocks.py --clean   # Elimina imatges que ja no s'utilitzen
    python3 scripts/render_blocks.py --force   # Força la regeneració de tots els blocs
"""

import sys
import os
import re
import json
import base64
import hashlib
import argparse
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
APUNTS_DIR = WORKSPACE_ROOT / "apunts"
OUTPUT_DIR = WORKSPACE_ROOT / "assets" / "images" / "blocks"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"

# Reordering JS script running inside Chrome canvas to place 'al iniciar' at the top
REORDER_JS = """
function reorderPngBlocks(dataUri, callback) {
  if (typeof dataUri !== "string" || dataUri.indexOf("data:image/png") === -1) {
    callback(dataUri);
    return;
  }
  var img = new Image();
  img.onload = function () {
    try {
      var w = img.naturalWidth || img.width;
      var h = img.naturalHeight || img.height;
      var canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      var ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);

      var imgData = ctx.getImageData(0, 0, w, h);
      var data = imgData.data;

      var rowHasContent = new Uint8Array(h);
      for (var y = 0; y < h; y++) {
        var rowOffset = y * w * 4;
        for (var x = 0; x < w; x++) {
          if (data[rowOffset + x * 4 + 3] > 10) {
            rowHasContent[y] = 1;
            break;
          }
        }
      }

      var slices = [];
      var inSlice = false;
      var startY = 0;
      for (var y = 0; y < h; y++) {
        if (rowHasContent[y] && !inSlice) {
          inSlice = true;
          startY = y;
        } else if (!rowHasContent[y] && inSlice) {
          inSlice = false;
          slices.push({ y1: startY, y2: y - 1 });
        }
      }
      if (inSlice) {
        slices.push({ y1: startY, y2: h - 1 });
      }

      if (slices.length <= 1) {
        callback(dataUri);
        return;
      }

      var startSliceIdx = -1;
      for (var i = 0; i < slices.length; i++) {
        var s = slices[i];
        var headerGreenCount = 0;
        var headerMaxY = Math.min(s.y2, s.y1 + 80);
        var headerMaxX = Math.min(w, 600);
        for (var sy = s.y1; sy <= headerMaxY; sy++) {
          var offset = sy * w * 4;
          for (var sx = 0; sx < headerMaxX; sx++) {
            var r = data[offset + sx * 4];
            var g = data[offset + sx * 4 + 1];
            var b = data[offset + sx * 4 + 2];
            var a = data[offset + sx * 4 + 3];
            if (a > 200 && r < 50 && g > 140 && b < 100) {
              headerGreenCount++;
            }
          }
        }
        if (headerGreenCount > 500) {
          startSliceIdx = i;
          break;
        }
      }

      if (startSliceIdx <= 0) {
        callback(dataUri);
        return;
      }

      var reorderedSlices = [slices[startSliceIdx]];
      for (var j = 0; j < slices.length; j++) {
        if (j !== startSliceIdx) reorderedSlices.push(slices[j]);
      }

      var gap = slices.length > 1 ? (slices[1].y1 - slices[0].y2) : 60;
      if (gap < 20) gap = 48;

      var totalHeight = 0;
      for (var k = 0; k < reorderedSlices.length; k++) {
        totalHeight += (reorderedSlices[k].y2 - reorderedSlices[k].y1 + 1);
        if (k > 0) totalHeight += gap;
      }

      var outCanvas = document.createElement("canvas");
      outCanvas.width = w;
      outCanvas.height = totalHeight;
      var outCtx = outCanvas.getContext("2d");

      var curY = 0;
      for (var m = 0; m < reorderedSlices.length; m++) {
        var sl = reorderedSlices[m];
        var sliceH = sl.y2 - sl.y1 + 1;
        outCtx.drawImage(canvas, 0, sl.y1, w, sliceH, 0, curY, w, sliceH);
        curY += sliceH + gap;
      }

      callback(outCanvas.toDataURL("image/png"));
    } catch (err) {
      console.warn("reorderPngBlocks error:", err);
      callback(dataUri);
    }
  };
  img.onerror = function () {
    callback(dataUri);
  };
  img.src = dataUri;
}
"""


def normalize_code(raw_code: str):
    """
    Normalitza el codi exactament igual que la funció de JavaScript.
    Retorna (hash_16, is_snippet, clean_code).
    """
    is_snippet = bool(re.search(r'//\s*(snippet|standalone|nostart|no-start)', raw_code, re.I))
    clean = raw_code
    if is_snippet:
        clean = re.sub(r'//\s*(snippet|standalone|nostart|no-start)[^\r\n]*', '', clean, flags=re.I)

    lines = [l.rstrip() for l in clean.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    while lines and lines[0] == '':
        lines.pop(0)
    while lines and lines[-1] == '':
        lines.pop()

    normalized = '\n'.join(lines)
    prefix = 'snippet:' if is_snippet else 'full:'
    content_hash = hashlib.sha256((prefix + normalized).encode('utf-8')).hexdigest()[:16]
    return content_hash, is_snippet, normalized


def find_all_blocks():
    """
    Cerca tots els blocs ```blocks ... ``` en els fitxers Markdown de apunts/.
    Retorna una llista de diccionaris amb la informació de cada bloc.
    """
    blocks = []
    seen_hashes = set()

    for md_path in sorted(APUNTS_DIR.glob("**/*.md")):
        content = md_path.read_text(encoding="utf-8")
        pattern = re.compile(r'```blocks[^\n]*\n(.*?)```', re.DOTALL)
        for match in pattern.finditer(content):
            raw_code = match.group(1)
            line_no = content[:match.start()].count('\n') + 1

            # Netejar prefix de blockquote si el bloc està dins d'un >
            cleaned_lines = []
            for l in raw_code.splitlines():
                cleaned_lines.append(re.sub(r'^\s*>\s?', '', l))
            cleaned_code = "\n".join(cleaned_lines)

            content_hash, is_snippet, normalized = normalize_code(cleaned_code)

            rel_path = md_path.relative_to(WORKSPACE_ROOT).as_posix()
            block_info = {
                "hash": content_hash,
                "is_snippet": is_snippet,
                "code": normalized,
                "file": rel_path,
                "line": line_no,
            }
            blocks.append(block_info)
            seen_hashes.add(content_hash)

    return blocks, seen_hashes


def render_blocks_headless(blocks_to_render):
    """
    Renderitza els blocs especificats utilitzant Chrome headless i MakeCode Arcade.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    print(f"-> Inicialitzant Chrome headless per renderitzar {len(blocks_to_render)} blocs...")
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=opts)
    try:
        print("-> Connectant amb https://arcade.makecode.com/--docs?render=1 ...")
        driver.get("https://arcade.makecode.com/--docs?render=1")

        # Configurar receptor de missatges i esperar 'renderready'
        setup_script = f"""
        {REORDER_JS}
        var callback = arguments[arguments.length - 1];
        window.renderedResults = {{}};
        window.addEventListener('message', function(e) {{
            if (!e.data || e.data.source !== 'makecode') return;
            if (e.data.type === 'renderready') {{
                window.isReady = true;
                callback(true);
            }} else if (e.data.type === 'renderblocks') {{
                var id = e.data.id;
                reorderPngBlocks(e.data.uri, function(finalUri) {{
                    window.renderedResults[id] = finalUri;
                }});
            }}
        }});
        """
        driver.execute_async_script(setup_script)
        print("-> MakeCode Arcade inicialitzat correctament!")

        render_single_script = """
        var callback = arguments[arguments.length - 1];
        var id = arguments[0];
        var code = arguments[1];
        var isSnippet = arguments[2];

        var payload = { type: 'renderblocks', id: id, code: code };
        if (isSnippet) payload.options = { snippetMode: true };

        window.postMessage(payload, '*');

        var start = Date.now();
        var iv = setInterval(function() {
            if (window.renderedResults[id]) {
                clearInterval(iv);
                var res = window.renderedResults[id];
                delete window.renderedResults[id];
                callback(res);
            } else if (Date.now() - start > 45000) {
                clearInterval(iv);
                callback(null);
            }
        }, 50);
        """

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        count = 0
        total = len(blocks_to_render)

        for blk in blocks_to_render:
            count += 1
            h = blk["hash"]
            print(f"[{count}/{total}] Renderitzant {h} ({blk['file']}:{blk['line']})...", end="", flush=True)

            uri = driver.execute_async_script(
                render_single_script,
                h,
                blk["code"],
                blk["is_snippet"],
            )

            if not uri or "data:image/png;base64," not in uri:
                print(" ERROR: no s'ha rebut la imatge en el temps límit.")
                continue

            # Descodificar i guardar PNG
            base64_data = uri.split("data:image/png;base64,")[1]
            png_bytes = base64.b64decode(base64_data)
            out_file = OUTPUT_DIR / f"{h}.png"
            out_file.write_bytes(png_bytes)
            print(f" FET ({len(png_bytes) // 1024} KB)")

    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Pre-renderitzador de blocs MakeCode per a Jekyll")
    parser.add_argument("--check", action="store_true", help="Comprova si tots els blocs estan renderitzats sense descarregar")
    parser.add_argument("--clean", action="store_true", help="Elimina imatges que ja no estan referenciades")
    parser.add_argument("--force", action="store_true", help="Força la re-generació de tots els blocs")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks, active_hashes = find_all_blocks()
    unique_blocks = {b["hash"]: b for b in blocks}

    print(f"Total de blocs trobats en Markdown: {len(blocks)} ({len(unique_blocks)} únics)")

    # Comprovar quins fitxers existeixen
    existing_pngs = {p.stem for p in OUTPUT_DIR.glob("*.png")}
    missing_hashes = [h for h in unique_blocks if h not in existing_pngs or args.force]

    if args.clean:
        orphans = existing_pngs - active_hashes
        if orphans:
            print(f"Eliminant {len(orphans)} imatges òrfenes...")
            for oph in orphans:
                (OUTPUT_DIR / f"{oph}.png").unlink(missing_ok=True)
        else:
            print("No hi ha imatges òrfenes per netejar.")

    if args.check:
        if missing_hashes:
            print(f"[ALERTA] Falten {len(missing_hashes)} blocs per renderitzar:")
            for h in missing_hashes:
                blk = unique_blocks[h]
                print(f"  - {h}: {blk['file']}:{blk['line']}")
            print("\nExecuta 'python3 scripts/render_blocks.py' per generar-los.")
            sys.exit(1)
        else:
            print("[OK] Tots els blocs estan pre-renderitzats i al dia.")
            sys.exit(0)

    if not missing_hashes:
        print("[OK] Tots els blocs estan al dia. No cal fer cap renderitzat.")
    else:
        blocks_to_render = [unique_blocks[h] for h in missing_hashes]
        render_blocks_headless(blocks_to_render)

    # Actualitzar manifest.json
    manifest = {}
    for b in blocks:
        h = b["hash"]
        manifest[h] = {
            "file": b["file"],
            "line": b["line"],
            "is_snippet": b["is_snippet"],
        }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"-> Manifest actualitzat a {MANIFEST_FILE.relative_to(WORKSPACE_ROOT)}")


if __name__ == "__main__":
    main()
