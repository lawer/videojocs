# Demos per a Animacions (Ús exclusiu del professorat)

Aquest directori conté els fitxers de codi font (`.ts`) que defineixen les animacions i demostracions visuals dels apunts.

## Privadesa i Seguretat Anticòpia
En començar pel caràcter de guió baix `_`, **Jekyll ignora aquest directori per defecte**. Això garanteix que:
- Cap d'aquests fitxers de codi es compila ni es publica a `_site/` ni al lloc web.
- L'alumnat **NO pot accedir al codi font** de les solucions ni a través del navegador ni amb F12.
- A la web només es publiquen les imatges `.gif` resultants a `assets/images/animations/`.

## Com afegir una nova animació
1. Crea un fitxer aquí, per exemple `_demos/moviment_sprite.ts`.
2. Escriu el codi de MakeCode Arcade que vols que s'executi.
3. Pots afegir capçaleres opcionals a l'inici:
   ```typescript
   // duration: 3.0
   // fps: 15
   // scale: 2
   // keys: right, down
   ```
4. Executa:
   ```bash
   python3 scripts/render_animations.py
   ```
5. La imatge resultant es guardarà a `assets/images/animations/moviment_sprite.gif`.
6. Enllaça-la al teu fitxer Markdown dels apunts:
   ```markdown
   ![Demostració](../../images/animations/moviment_sprite.gif)
   ```
