import React from 'react';

import { cores } from '../config';

/** Tela do app no vídeo; os prints têm 412 × 892 px de layout. */
export const LARGURA_TELA = 400;
export const ALTURA_TELA = Math.round((LARGURA_TELA * 892) / 412);
export const ESCALA_TELA = LARGURA_TELA / 412;
const MOLDURA = 16;

/** Posição do celular nas cenas 3, 4 e 5, para a troca de tela parecer contínua. */
export const POSICAO_CELULAR = { x: 560, y: 800 };
/** Canto superior esquerdo da tela, em coordenadas do vídeo. */
export const ORIGEM_TELA = { x: POSICAO_CELULAR.x + MOLDURA, y: POSICAO_CELULAR.y + MOLDURA };

type Props = {
  children: React.ReactNode;
  x?: number;
  y?: number;
  corBrilho?: string;
  forcaBrilho?: number;
  deslocamentoX?: number;
};

export const Celular: React.FC<Props> = ({
  children,
  x = POSICAO_CELULAR.x,
  y = POSICAO_CELULAR.y,
  corBrilho = cores.tecnico,
  forcaBrilho = 0,
  deslocamentoX = 0,
}) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: LARGURA_TELA + MOLDURA * 2,
      height: ALTURA_TELA + MOLDURA * 2,
      padding: MOLDURA,
      borderRadius: 68,
      background: 'linear-gradient(155deg, #3A4755 0%, #141A21 22%, #07090C 70%, #1A2129 100%)',
      border: '2px solid #4A5766',
      boxShadow: `0 50px 90px rgba(0, 0, 0, 0.65), 0 0 ${90 * forcaBrilho}px ${26 * forcaBrilho}px ${corBrilho}`,
      transform: `translateX(${deslocamentoX}px)`,
    }}
  >
    {/* botões laterais */}
    <div style={{ position: 'absolute', right: -6, top: 190, width: 6, height: 90, borderRadius: 3, background: '#2A3440' }} />
    <div style={{ position: 'absolute', right: -6, top: 300, width: 6, height: 140, borderRadius: 3, background: '#2A3440' }} />
    <div
      style={{
        position: 'relative',
        width: LARGURA_TELA,
        height: ALTURA_TELA,
        borderRadius: 52,
        overflow: 'hidden',
        backgroundColor: cores.fundo,
      }}
    >
      {children}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(125deg, rgba(255, 255, 255, 0.07) 0%, transparent 32%)',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 14,
          left: '50%',
          width: 18,
          height: 18,
          marginLeft: -9,
          borderRadius: 9,
          backgroundColor: '#000',
          boxShadow: '0 0 0 3px #10151B',
        }}
      />
    </div>
  </div>
);
