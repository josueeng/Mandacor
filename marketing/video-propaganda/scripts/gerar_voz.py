#!/usr/bin/env python3
"""Gera a narração do vídeo com o edge-tts (vozes neurais gratuitas da Microsoft).

Uso:
  python scripts/gerar_voz.py
  python scripts/gerar_voz.py --voz pt-BR-FranciscaNeural --taxa +0%

Os textos vêm de narracao.json. Para cada cena são criados, em public/voz/:
  cena-N.mp3 / cena-N.json              versão completa
  curta-cena-N.mp3 / curta-cena-N.json  versão curta
O .json guarda o tempo de cada palavra, usado na legenda palavra a palavra.

Requer: pip install edge-tts (e internet). Usa o ffmpeg do sistema ou o do Remotion
(npm install nesta pasta) para cortar o silêncio do fim de cada fala e igualar o volume.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from ffmpeg_util import rodar_ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
PASTA_VOZ = RAIZ / "public" / "voz"
PREFIXOS = {"completa": "cena-", "curta": "curta-cena-"}
# Silêncio mantido depois da última palavra; o resto do silêncio do edge-tts é cortado,
# porque a duração de cada cena vem do tamanho do arquivo de áudio.
SILENCIO_FINAL = 0.12
# Volume da fala (LUFS) e pico máximo, perto do padrão de Reels e TikTok.
NORMALIZACAO = "loudnorm=I=-16:TP=-1.5:LRA=11"

try:
    import edge_tts
except ImportError:
    sys.exit("edge-tts não está instalado. Rode: pip install edge-tts")


async def sintetizar(texto, voz, taxa, destino_mp3, destino_json):
    comunicacao = edge_tts.Communicate(
        texto,
        voz,
        rate=taxa,
        boundary="WordBoundary",
        # Só usado quando a máquina sai para a internet por um proxy.
        proxy=os.environ.get("HTTPS_PROXY") or None,
    )
    palavras = []
    with open(destino_mp3, "wb") as arquivo:
        async for parte in comunicacao.stream():
            if parte["type"] == "audio":
                arquivo.write(parte["data"])
            elif parte["type"] == "WordBoundary":
                # Os tempos do edge-tts vêm em unidades de 100 ns.
                inicio = parte["offset"] / 10_000_000
                fim = inicio + parte["duration"] / 10_000_000
                palavras.append({"texto": parte["text"], "inicio": round(inicio, 3), "fim": round(fim, 3)})
    if palavras:
        bruto = destino_mp3.with_suffix(".bruto.mp3")
        destino_mp3.replace(bruto)
        rodar_ffmpeg("-i", str(bruto), "-t", f"{palavras[-1]['fim'] + SILENCIO_FINAL:.3f}",
                     "-af", NORMALIZACAO, "-ar", "44100",
                     "-codec:a", "libmp3lame", "-b:a", "128k", str(destino_mp3))
        bruto.unlink()
    with open(destino_json, "w", encoding="utf-8") as arquivo:
        json.dump({"texto": texto, "voz": voz, "taxa": taxa, "palavras": palavras}, arquivo, ensure_ascii=False, indent=2)
    return palavras


async def principal():
    narracao = json.loads((RAIZ / "narracao.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description="Gera a narração do vídeo MANDACOR.")
    parser.add_argument("--voz", default=narracao.get("voz", "pt-BR-AntonioNeural"))
    parser.add_argument("--taxa", default=narracao.get("taxa", "+5%"), help='velocidade, ex.: "+5%%" ou "-10%%"')
    args = parser.parse_args()

    PASTA_VOZ.mkdir(parents=True, exist_ok=True)
    for versao, prefixo in PREFIXOS.items():
        for cena, texto in narracao[versao].items():
            mp3 = PASTA_VOZ / f"{prefixo}{cena}.mp3"
            palavras = await sintetizar(texto, args.voz, args.taxa, mp3, mp3.with_suffix(".json"))
            fim = palavras[-1]["fim"] if palavras else 0
            print(f"{versao:9} cena {cena}: {fim:4.1f} s  {texto}")


if __name__ == "__main__":
    asyncio.run(principal())
