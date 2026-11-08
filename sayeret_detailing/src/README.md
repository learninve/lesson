Rebuild: put base files in one dir, set PHONE (e.g. `PHONE=050-1234567 python3 -I text_layers.py`), then `python3 -I clean.py && bash build.sh`.
clean.py: removes the burned-in English captions ("$400 is too much 🤣" 0–1.45s, "Uhhhh....." 1.45–3.7s) by inpainting, 720p→1080x1920 lanczos with 100→108% zoom.
text_layers.py: Hebrew RTL text layers (Pillow+Raqm, Heebo ExtraBold). build.sh: grade, overlays, end card, loudnorm -14 LUFS, encode.
