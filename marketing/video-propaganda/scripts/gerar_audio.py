#!/usr/bin/env python3
"""Gera, por código, a trilha e os efeitos sonoros do vídeo (sem direitos de terceiros).

Uso:
  python scripts/gerar_audio.py

Cria:
  public/musica-gerada.mp3   pulso eletrônico calmo, 100 BPM, baixo + pad (48 s)
  public/sfx/whoosh.wav      transição de cena
  public/sfx/alerta.wav      "FICOU PIOR"
  public/sfx/sucesso.wav     "MELHOROU"
  public/sfx/clique.wav      celular entrando na tela

Se existir public/musica.mp3, o vídeo usa essa música no lugar da gerada.
Requer: pip install numpy. O MP3 usa o ffmpeg do sistema ou o do Remotion.
"""
import sys
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:
    sys.exit("numpy não está instalado. Rode: pip install numpy")

from ffmpeg_util import rodar_ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
TAXA = 44100
BPM = 100
TEMPO = 60 / BPM  # duração de uma batida (s)
DURACAO_MUSICA = 48.0
RNG = np.random.default_rng(7)

# Progressão em lá menor, um acorde por compasso: Am - F - C - G.
ACORDES = [
    (57, 60, 64),  # A3 C4 E4
    (53, 57, 60),  # F3 A3 C4
    (55, 60, 64),  # G3 C4 E4 (C/G)
    (55, 59, 62),  # G3 B3 D4
]
BAIXOS = [45, 41, 36, 43]  # A2 F2 C2 G2


def hz(nota_midi):
    return 440.0 * 2 ** ((nota_midi - 69) / 12)


def salvar_wav(caminho, estereo):
    estereo = np.clip(estereo, -1, 1)
    dados = (estereo * 32767).astype("<i2")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(dados.tobytes())


def normalizar(sinal, pico=0.89):
    maximo = np.max(np.abs(sinal))
    return sinal if maximo == 0 else sinal * (pico / maximo)


def passa_baixa(sinal, corte_hz):
    """Filtro passa-baixa suave feito no domínio da frequência."""
    espectro = np.fft.rfft(sinal)
    freqs = np.fft.rfftfreq(len(sinal), 1 / TAXA)
    espectro *= 1 / np.sqrt(1 + (freqs / corte_hz) ** 4)
    return np.fft.irfft(espectro, len(sinal))


def passa_alta(sinal, corte_hz):
    return sinal - passa_baixa(sinal, corte_hz)


def tom(freq, duracao, harmonicos=(1.0,), fase=0.0):
    t = np.arange(int(duracao * TAXA)) / TAXA
    onda = np.zeros_like(t)
    for n, amplitude in enumerate(harmonicos, start=1):
        onda += amplitude * np.sin(2 * np.pi * freq * n * t + fase * n)
    return onda


def colocar(destino, sinal, inicio_s, ganho=1.0):
    i = int(inicio_s * TAXA)
    fim = min(len(destino), i + len(sinal))
    if i < fim:
        destino[i:fim] += sinal[: fim - i] * ganho


def gerar_musica():
    total = int(DURACAO_MUSICA * TAXA)
    esquerda = np.zeros(total)
    direita = np.zeros(total)
    compasso = 4 * TEMPO
    t_total = np.arange(total) / TAXA

    # Pad: tríade com vozes levemente desafinadas entre os canais, entrada lenta.
    for indice in range(int(DURACAO_MUSICA / compasso) + 1):
        inicio = indice * compasso
        acorde = ACORDES[indice % len(ACORDES)]
        duracao = compasso + 0.6
        n = int(duracao * TAXA)
        t = np.arange(n) / TAXA
        envelope = np.minimum(1, t / 0.5) * np.minimum(1, (duracao - t) / 0.6)
        for nota in acorde:
            for canal, desafino in ((esquerda, -0.12), (direita, 0.12)):
                f = hz(nota) * 2 ** (desafino / 12)
                colocar(canal, tom(f, duracao, (1, 0.5, 0.3, 0.15, 0.08)) * envelope, inicio, 0.09)

    # Respiração do pad no ritmo do bumbo (sidechain suave).
    fase_batida = (t_total % TEMPO)
    respiro = 1 - 0.35 * np.exp(-fase_batida / 0.14)
    esquerda *= respiro
    direita *= respiro
    esquerda = passa_baixa(esquerda, 3500)
    direita = passa_baixa(direita, 3500)

    centro = np.zeros(total)
    entrada_ritmo = 2 * compasso  # bumbo e baixo entram no terceiro compasso

    # Bumbo em todas as batidas, curto e macio.
    n = int(0.35 * TAXA)
    t = np.arange(n) / TAXA
    freq = 48 + 70 * np.exp(-t / 0.03)
    bumbo = np.sin(2 * np.pi * np.cumsum(freq) / TAXA) * np.exp(-t / 0.16)
    batida = entrada_ritmo
    while batida < DURACAO_MUSICA:
        colocar(centro, bumbo, batida, 0.32)
        batida += TEMPO

    # Baixo pulsando em colcheias, nota fundamental do acorde.
    n = int(TEMPO / 2 * TAXA)
    t = np.arange(n) / TAXA
    envelope = np.minimum(1, t / 0.006) * (0.45 + 0.55 * np.exp(-t / 0.12)) * np.minimum(1, (TEMPO / 2 - t) / 0.02)
    colcheia = entrada_ritmo
    contagem = 0
    while colcheia < DURACAO_MUSICA:
        indice = int(colcheia / compasso) % len(BAIXOS)
        nota = BAIXOS[indice] + (12 if contagem % 8 == 7 else 0)
        # Harmônicos fortes para o baixo aparecer também no alto-falante do celular.
        onda = np.tanh(2.2 * tom(hz(nota), TEMPO / 2, (1, 0.45, 0.2))) * envelope
        colocar(centro, onda, colcheia, 0.17 if contagem % 2 else 0.13)
        colcheia += TEMPO / 2
        contagem += 1
    centro = passa_baixa(centro, 1400)  # suaviza o ataque sem tirar o corpo

    # Chimbal no contratempo.
    n = int(0.06 * TAXA)
    t = np.arange(n) / TAXA
    chimbal = passa_alta(RNG.standard_normal(n), 7000) * np.exp(-t / 0.018)
    batida = TEMPO / 2
    while batida < DURACAO_MUSICA:
        colocar(esquerda, chimbal, batida, 0.06)
        colocar(direita, chimbal, batida, 0.06)
        batida += TEMPO

    # Arpejo leve a partir do quinto compasso, alternando os lados.
    n = int(TEMPO / 4 * TAXA * 2)
    t = np.arange(n) / TAXA
    envelope = np.minimum(1, t / 0.004) * np.exp(-t / 0.11)
    semicolcheia = 4 * compasso
    passo = 0
    while semicolcheia < DURACAO_MUSICA:
        acorde = ACORDES[int(semicolcheia / compasso) % len(ACORDES)]
        nota = (acorde + (acorde[0] + 12,))[[0, 1, 2, 3, 2, 1, 0, 2][passo % 8]] + 12
        onda = tom(hz(nota), len(t) / TAXA, (1, 0.2)) * envelope
        lado = esquerda if passo % 2 else direita
        colocar(lado, onda, semicolcheia, 0.09)
        colocar(esquerda if lado is direita else direita, onda, semicolcheia, 0.035)
        semicolcheia += TEMPO / 4
        passo += 1

    estereo = np.stack([esquerda + centro, direita + centro], axis=1)
    estereo = np.tanh(1.3 * normalizar(estereo)) / np.tanh(1.3)
    estereo = normalizar(estereo)
    wav = RAIZ / "public" / "musica-gerada.wav"
    salvar_wav(wav, estereo)
    mp3 = RAIZ / "public" / "musica-gerada.mp3"
    rodar_ffmpeg("-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3))
    wav.unlink()
    print(f"musica: {mp3.relative_to(RAIZ)} ({DURACAO_MUSICA:.0f} s)")


def gerar_whoosh():
    duracao = 0.5
    n = int(duracao * TAXA)
    t = np.arange(n) / TAXA
    ruido = RNG.standard_normal(n)
    grave = passa_baixa(ruido, 900)
    agudo = passa_alta(passa_baixa(ruido, 6000), 1500)
    subida = np.clip(t / 0.3, 0, 1)
    mistura = grave * (1 - subida) + agudo * subida * 0.8
    envelope = np.sin(np.pi * np.clip(t / duracao, 0, 1)) ** 2
    sinal = normalizar(mistura * envelope, 0.8)
    pan = np.clip(t / duracao, 0, 1)
    salvar_wav(RAIZ / "public" / "sfx" / "whoosh.wav", np.stack([sinal * (1 - 0.6 * pan), sinal * (0.4 + 0.6 * pan)], axis=1))


def gerar_alerta():
    duracao = 0.6
    sinal = np.zeros(int(duracao * TAXA))
    for inicio in (0.0, 0.22):
        n = int(0.3 * TAXA)
        t = np.arange(n) / TAXA
        freq = 170 * (1 - 0.15 * t / 0.3)
        fase = 2 * np.pi * np.cumsum(freq) / TAXA
        pulso = np.tanh(2.5 * np.sin(fase)) * 0.6 + np.sin(fase / 2) * 0.5
        pulso *= np.minimum(1, t / 0.004) * np.exp(-t / 0.09)
        colocar(sinal, pulso, inicio)
    sinal = normalizar(passa_baixa(sinal, 2500), 0.85)
    salvar_wav(RAIZ / "public" / "sfx" / "alerta.wav", np.stack([sinal, sinal], axis=1))


def gerar_sucesso():
    duracao = 0.8
    sinal = np.zeros(int(duracao * TAXA))
    for inicio, nota in ((0.0, 81), (0.12, 88)):  # A5 e E6, subindo
        n = int(0.6 * TAXA)
        t = np.arange(n) / TAXA
        onda = tom(hz(nota), 0.6, (1, 0.25, 0.08)) * np.minimum(1, t / 0.005) * np.exp(-t / 0.17)
        colocar(sinal, onda, inicio)
    brilho = tom(hz(93), 0.5, (1,)) * np.exp(-np.arange(int(0.5 * TAXA)) / TAXA / 0.12)
    colocar(sinal, brilho, 0.12, 0.15)
    sinal = normalizar(sinal, 0.8)
    salvar_wav(RAIZ / "public" / "sfx" / "sucesso.wav", np.stack([sinal, sinal], axis=1))


def gerar_clique():
    duracao = 0.08
    n = int(duracao * TAXA)
    t = np.arange(n) / TAXA
    estalo = passa_alta(RNG.standard_normal(n), 3000) * np.exp(-t / 0.004)
    corpo = np.sin(2 * np.pi * 1800 * t) * np.exp(-t / 0.01)
    sinal = normalizar(estalo * 0.6 + corpo * 0.5, 0.8)
    salvar_wav(RAIZ / "public" / "sfx" / "clique.wav", np.stack([sinal, sinal], axis=1))


if __name__ == "__main__":
    gerar_musica()
    for gerar in (gerar_whoosh, gerar_alerta, gerar_sucesso, gerar_clique):
        gerar()
    print("efeitos: public/sfx/whoosh.wav, alerta.wav, sucesso.wav, clique.wav")
