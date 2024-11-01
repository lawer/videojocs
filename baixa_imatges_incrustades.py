import os
import requests

def listar_markdowns(directorio):
    markdown_files = []
    for root, dirs, files in os.walk(directorio):
        for file in files:
            if file.endswith('.md'):
                markdown_files.append(os.path.join(root, file))
    return markdown_files

def download_images_and_substitute(fichero):

    with open(fichero, 'r') as file:
        lines = file.readlines()
    for i, line in enumerate(lines):
        if line.startswith('!['):
            url = line.split('(')[1].split(')')[0]
            if url.startswith('http'):
                # Baixem la imatge amb requests

                response = requests.get(url)
                
                # Guardem la imatge en un directori local
                filename = f'downloaded_{url.split("/")[-1]}'
                with open(f'apunts/images/{filename}', 'wb') as file:
                    file.write(response.content)
                
                
                # Modifiquem la línia perquè apunti a la imatge local
                new_url = f'../../images/{filename}'
                lines[i] = line.replace(url, new_url)

    with open(fichero, 'w') as file:
        file.writelines(lines)    


# Ejemplo de uso
directorio = 'apunts'
ficheros = listar_markdowns(directorio)

for fichero in ficheros:
    download_images_and_substitute(fichero)
    
print(ficheros)