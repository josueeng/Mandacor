import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';

import { cores } from '../config';
import { fonteTitulo } from '../fontes';

const semPontuacao = (palavra: string) => palavra.replace(/[.,!?;:]+$/, '');

/** Índices das palavras do título que formam o trecho destacado (ignora pontuação final). */
function indicesDoDestaque(palavras: string[], destaque?: string): Set<number> {
  if (!destaque) return new Set();
  const alvo = destaque.split(' ').map(semPontuacao);
  for (let i = 0; i + alvo.length <= palavras.length; i++) {
    if (alvo.every((palavra, j) => semPontuacao(palavras[i + j]) === palavra)) {
      return new Set(alvo.map((_, j) => i + j));
    }
  }
  return new Set();
}

type Props = {
  texto: string;
  destaque?: string;
  corDestaque?: string;
  atraso?: number;
  topo?: number;
  tamanho?: number;
};

/** Título grande que entra palavra a palavra, de baixo para cima. */
export const Titulo: React.FC<Props> = ({
  texto,
  destaque,
  corDestaque = cores.tecnico,
  atraso = 0,
  topo = 206,
  tamanho = 112,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const palavras = texto.split(' ');
  const marcadas = indicesDoDestaque(palavras, destaque);
  return (
    <div
      style={{
        position: 'absolute',
        top: topo,
        left: 80,
        right: 80,
        fontFamily: fonteTitulo,
        fontSize: tamanho,
        lineHeight: 1.04,
        letterSpacing: -1.5,
        color: cores.texto,
        textWrap: 'balance',
      }}
    >
      {palavras.map((palavra, i) => {
        const entrada = spring({ frame: frame - atraso - i * 3, fps, config: { damping: 200 }, durationInFrames: 14 });
        return (
          <React.Fragment key={i}>
            {i > 0 && ' '}
            <span
              style={{
                display: 'inline-block',
                opacity: entrada,
                transform: `translateY(${(1 - entrada) * 46}px)`,
                color: marcadas.has(i) ? corDestaque : undefined,
              }}
            >
              {palavra}
            </span>
          </React.Fragment>
        );
      })}
    </div>
  );
};
