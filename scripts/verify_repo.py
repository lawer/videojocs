#!/usr/bin/env python3
"""
Validador de consistència per al repositori del Taller de Videojocs.
Comprova:
1. Enllaços interns entre documents Markdown.
2. Imatges relatives referenciades en Markdown.
3. Jerarquia de navegació (parent/grand_parent existents i sense duplicats de nav_order).
"""

import os
import re
import sys
import yaml
from collections import defaultdict


def check_images_and_links(base_dir="apunts"):
    errors = []
    checked_files = 0

    for root, _, files in os.walk(base_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            checked_files += 1
            file_path = os.path.join(root, f)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()

            # 1. Comprovar imatges relatives ![alt](url)
            for m in re.finditer(r"!\[(.*?)\]\((.*?)\)", content):
                url = m.group(2).strip().split()[0]
                if url.startswith("http://") or url.startswith("https://"):
                    continue
                resolved = os.path.normpath(os.path.join(root, url))
                if not os.path.exists(resolved):
                    errors.append(f"[IMATGE TRENCADA] {file_path} -> {url} (no trobat a {resolved})")

            # 2. Comprovar enllaços interns [text](url)
            for m in re.finditer(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", content):
                url = m.group(2).strip().split()[0].split("#")[0]
                if not url or url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:"):
                    continue
                resolved = os.path.normpath(os.path.join(root, url))
                if not os.path.exists(resolved):
                    errors.append(f"[ENLLAÇ TRENCAT] {file_path} -> {url} (no trobat a {resolved})")

    return checked_files, errors


def check_navigation(base_dir="."):
    errors = []
    groups = defaultdict(list)
    pages = []

    for root, _, files in os.walk(base_dir):
        if any(ignored in root for ignored in [".git", "_site", ".jekyll-cache", "vendor", "_arxiu"]):
            continue
        for f in files:
            if not f.endswith(".md"):
                continue
            file_path = os.path.join(root, f)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                lines = fp.readlines()
            if lines and lines[0].strip() == "---":
                fm_lines = []
                for line in lines[1:]:
                    if line.strip() == "---":
                        break
                    fm_lines.append(line)
                try:
                    data = yaml.safe_load("".join(fm_lines)) or {}
                    page_info = {
                        "path": file_path,
                        "title": data.get("title"),
                        "parent": data.get("parent"),
                        "grand_parent": data.get("grand_parent"),
                        "nav_order": data.get("nav_order"),
                    }
                    pages.append(page_info)
                    key = (data.get("grand_parent"), data.get("parent"))
                    groups[key].append(page_info)
                except Exception as e:
                    errors.append(f"[YAML ERROR] {file_path}: {e}")

    all_titles = {p["title"] for p in pages if p["title"]}

    for p in pages:
        if p["parent"] and p["parent"] not in all_titles:
            errors.append(f"[PARENT DESCONEGUT] {p['path']}: parent '{p['parent']}' no existeix")
        if p["grand_parent"] and p["grand_parent"] not in all_titles:
            errors.append(f"[GRAND_PARENT DESCONEGUT] {p['path']}: grand_parent '{p['grand_parent']}' no existeix")

    for key, items in groups.items():
        orders = [x["nav_order"] for x in items if x["nav_order"] is not None]
        duplicates = set([o for o in orders if orders.count(o) > 1])
        for dup in duplicates:
            conflicting = [x["path"] for x in items if x["nav_order"] == dup]
            errors.append(f"[NAV_ORDER DUPLICAT] Al grup {key}, nav_order {dup} duplicat a: {conflicting}")

    return len(pages), errors


def main():
    print("Iniciant verificació del repositori...")
    files_checked, content_errors = check_images_and_links()
    pages_checked, nav_errors = check_navigation()

    all_errors = content_errors + nav_errors

    print(f"- Fitxers Markdown revisats: {files_checked}")
    print(f"- Pàgines amb navegació revisades: {pages_checked}")

    if all_errors:
        print(f"\nS'han trobat {len(all_errors)} errors:")
        for err in all_errors:
            print(f"  ❌ {err}")
        sys.exit(1)
    else:
        print("\n✅ Verificació completada amb èxit: 0 errors detectats.")
        sys.exit(0)


if __name__ == "__main__":
    main()
