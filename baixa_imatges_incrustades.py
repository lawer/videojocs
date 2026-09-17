import os
import re
import urllib.parse
import urllib.request


def listar_markdowns(directorio):
    markdown_files = []
    for root, dirs, files in os.walk(directorio):
        for file in files:
            if file.endswith(".md"):
                markdown_files.append(os.path.join(root, file))
    return sorted(markdown_files)


def download_images_and_substitute(fichero, images_dir="apunts/images"):
    with open(fichero, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex que captura ![alt](url)
    pattern = re.compile(r"!\[(.*?)\]\((https?://[^\s\)]+)\)")
    modified = False

    def replacer(match):
        nonlocal modified
        alt_text = match.group(1)
        url = match.group(2)

        # Ometem badges dinàmics com shields.io
        if "shields.io" in url or "badge" in url:
            return match.group(0)

        # Extreure nom del fitxer net
        parsed_url = urllib.parse.urlparse(url)
        raw_filename = os.path.basename(parsed_url.path)
        if not raw_filename:
            return match.group(0)

        filename_fixed = f"downloaded_{raw_filename}"
        local_image_path = os.path.join(images_dir, filename_fixed)

        # Descarregar la imatge si no existeix ja localment
        if not os.path.exists(local_image_path):
            print(f"Descarregant: {url} -> {local_image_path}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req) as resp:
                    with open(local_image_path, "wb") as img_out:
                        img_out.write(resp.read())
            except Exception as e:
                print(f"Error descarregant {url}: {e}")
                return match.group(0)

        # Calcular el camí relatiu exacte des del document fins a la imatge
        doc_dir = os.path.dirname(fichero)
        relative_path = os.path.relpath(local_image_path, doc_dir)

        modified = True
        return f"![{alt_text}]({relative_path})"

    new_content = pattern.sub(replacer, content)

    if modified:
        with open(fichero, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Actualitzat: {fichero}")


if __name__ == "__main__":
    directorio = "apunts"
    ficheros = listar_markdowns(directorio)
    for fichero in ficheros:
        download_images_and_substitute(fichero)
    print("Processament finalitzat.")
