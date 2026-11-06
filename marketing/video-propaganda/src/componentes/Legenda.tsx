import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';

import { cores } from '../config';
import { fonteTexto } from '../fontes';
import { Palavra } from '../tipos';

/** Momento (s) em que cada palavra do texto começa a ser falada. */
function iniciosDasPalavras(tokens: string[], palavras: Palavra[] | null, segundos: number): number[] {
  if (palavras && palavras.length === tokens.length) return palavras.map((p) => p.inicio);
  if (palavras && palavras.length > 1) {
    // Quantidades diferentes (ex.: pontuação separada): distribui proporcionalmente.
    return tokens.map((_, j) => palavras[Math.round((j * (palavras.length - 1)) / Math.max(1, tokens.length - 1))].inicio);
  }
  return tokens.map((_, j) => (j * segundos) / tokens.length);
}

type Props = { texto: string; palavras: Palavra[] | null; segundos: number };

/** Legenda da narração com a palavra falada em destaque, acima da área que o Instagram cobre. */
export const Legenda: React.FC<Props> = ({ texto, palavras, segundos }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tempo = frame / fps;
  const tokens = texto.split(/\s+/);
  const inicios = iniciosDasPalavras(tokens, palavras, segundos);
  const fimDaFala = palavras?.length ? palavras[palavras.length - 1].fim : segundos;
  const atual = tempo > fimDaFala ? tokens.length : inicios.filter((inicio) => tempo >= inicio).length - 1;
  const entrada = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 10 });

  return (
    <div
      style={{
        position: 'absolute',
        left: 80,
        right: 80,
        bottom: 330,
        padding: '22px 34px',
        backgroundColor: 'rgba(18, 23, 29, 0.85)',
        border: `2px solid ${cores.borda}`,
        borderRadius: 28,
        fontFamily: fonteTexto,
        fontWeight: 800,
        fontSize: 52,
        lineHeight: 1.3,
        textAlign: 'center',
        opacity: entrada,
        transform: `translateY(${(1 - entrada) * 24}px)`,
      }}
    >
      {tokens.map((token, i) => (
        <React.Fragment key={i}>
          {i > 0 && ' '}
          <span
            style={{
              color: i < atual ? cores.texto : i === atual ? cores.fundo : cores.textoSecundario,
              backgroundColor: i === atual ? cores.tecnico : 'transparent',
              borderRadius: 10,
              padding: '0 0.14em',
              margin: '0 -0.14em',
            }}
          >
            {token}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
};
