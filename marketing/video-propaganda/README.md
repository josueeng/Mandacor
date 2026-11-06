# Vídeo de propaganda do MANDACOR

Vídeo vertical (1080 × 1920, 30 fps) feito com [Remotion](https://www.remotion.dev), em duas versões:

| Composição | Cenas | Duração | Arquivo |
|---|---|---|---|
| `Completa` | 1 a 6 | ~29 s | `out/mandacor-30s.mp4` |
| `Curta` | 1, 3, 4, 5 e 6 | ~16 s | `out/mandacor-15s.mp4` |

A duração de cada cena vem do tamanho real da narração, mais 0,6 s de pausa. A versão curta usa falas mais curtas (em `narracao.json`), porque com o texto completo ela passaria de 24 s.

## Requisitos

- Node.js 18 ou mais novo
- Python 3.10 ou mais novo, com `pip install edge-tts numpy` (só para gerar voz, música e efeitos)
- Internet na primeira renderização: o Remotion baixa o navegador que usa para desenhar os quadros

```bash
npm install
```

## Renderizar

```bash
npm run render        # as duas versões
npm run render:30s    # só a completa
npm run render:15s    # só a curta
npm run studio        # abre o editor no navegador para ver e ajustar
```

## Trocar o WhatsApp e os textos

Edite `src/config.ts`:

- `whatsapp`: número do cartão final;
- `textos`: títulos e frases de cada cena;
- `volumes`: voz, música (com e sem fala) e efeitos.

Depois renderize de novo.

## Trocar a voz

As falas ficam em `narracao.json`. Depois de mudar o texto ou a voz:

```bash
python scripts/gerar_voz.py
python scripts/gerar_voz.py --voz pt-BR-FranciscaNeural --taxa +0%
```

No Linux, use `python3`. O script grava `public/voz/cena-N.mp3` (e `curta-cena-N.mp3`), corta o silêncio do fim, iguala o volume e salva o tempo de cada palavra em `.json`, usado na legenda.

Para usar a sua própria gravação, substitua os `.mp3` em `public/voz/` mantendo os nomes. A legenda continua funcionando, com o destaque das palavras distribuído pelo tempo da fala.

## Trocar a música

Coloque um arquivo em `public/musica.mp3`: ele substitui a trilha gerada. Para refazer a trilha e os efeitos sonoros gerados por código:

```bash
python scripts/gerar_audio.py
```

## Telas do app

Os prints reais do app ficam em `public/prints/` (`resultados.png`, `ficou_pior.png`, `melhorou.png`, com 1236 × 2676 px). O arquivo `resultados.json` marca a linha destacada na cena 3. Sem os prints, ou com `usarPrints: false` em `src/config.ts`, o vídeo recria essas telas com as cores do app.

## Licenças e uso comercial

- **Fontes** (Archivo Black, Inter, Space Mono): licença SIL OFL, em `public/fontes/`.
- **Música e efeitos**: gerados por `scripts/gerar_audio.py`, sem material de terceiros.
- **Voz**: o edge-tts usa o serviço de leitura em voz alta do navegador Microsoft Edge, sem contrato de uso comercial. Para anúncio pago, prefira gravar a sua voz ou usar um serviço de voz com licença comercial.
- **Remotion**: gratuito para pessoas físicas e empresas com até 3 funcionários; acima disso exige a licença de empresa (remotion.pro).
