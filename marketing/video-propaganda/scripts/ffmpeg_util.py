"""Finds an ffmpeg to use: the system one, or the copy bundled with Remotion."""
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def comando_ffmpeg():
    sistema = shutil.which("ffmpeg")
    if sistema:
        return [sistema]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        return [npx, "remotion", "ffmpeg"]
    return None


def rodar_ffmpeg(*argumentos):
    comando = comando_ffmpeg()
    if comando is None:
        raise RuntimeError("ffmpeg não encontrado. Rode npm install nesta pasta ou instale o ffmpeg.")
    subprocess.run([*comando, "-hide_banner", "-loglevel", "error", "-y", *argumentos], check=True, cwd=RAIZ)
