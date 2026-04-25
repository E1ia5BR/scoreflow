"""
pdf_export.py
=============
Generates a PDF from a MusicXML file using available system tools.

Tries in order:
  1. MuseScore CLI (mscore / musescore4) — best quality
  2. music21's built-in LilyPond integration
  3. Returns None if no tool is available
"""

import os
import subprocess
import shutil


def generate_pdf(musicxml_path: str, output_pdf_path: str) -> bool:
    """
    Try to generate a PDF from a MusicXML file.

    Parameters
    ----------
    musicxml_path  : Path to the input .musicxml file.
    output_pdf_path: Desired path for the output .pdf file.

    Returns
    -------
    True if PDF was generated successfully, False otherwise.
    """
    # --- Attempt 1: MuseScore CLI ---
    musescore_names = ["mscore", "musescore", "musescore4", "MuseScore4"]
    for name in musescore_names:
        exe = shutil.which(name)
        if exe:
            try:
                result = subprocess.run(
                    [exe, "-o", output_pdf_path, musicxml_path],
                    capture_output=True,
                    timeout=120,
                )
                if result.returncode == 0 and os.path.exists(output_pdf_path):
                    print(f"[pdf_export] PDF generated via MuseScore ({name})", flush=True)
                    return True
                else:
                    print(f"[pdf_export] MuseScore ({name}) failed: {result.stderr.decode()[:200]}", flush=True)
            except Exception as e:
                print(f"[pdf_export] MuseScore ({name}) error: {e}", flush=True)

    # --- Attempt 2: music21 + LilyPond ---
    lilypond_exe = shutil.which("lilypond")
    if lilypond_exe:
        try:
            import music21
            music21.environment.set("lilypondPath", lilypond_exe)
            score = music21.converter.parse(musicxml_path)
            # music21 writes to a temp file, we move it
            lily_path = score.write("lily.pdf")
            if lily_path and os.path.exists(str(lily_path)):
                shutil.move(str(lily_path), output_pdf_path)
                print("[pdf_export] PDF generated via LilyPond", flush=True)
                return True
        except Exception as e:
            print(f"[pdf_export] LilyPond export failed: {e}", flush=True)

    print("[pdf_export] No PDF generator available (install MuseScore or LilyPond)", flush=True)
    return False
