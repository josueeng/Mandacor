import React from 'react';

import { cores } from '../config';
import { fonteTexto, fonteTitulo } from '../fontes';
import { comTransparencia } from '../util';

type Props = {
  titulo?: string;
  texto: string;
  cor: string;
  /** 0 a 1: entrada do cartão. */
  progresso: number;
  esquerda?: number;
  topo: number;
  largura?: number;
  centralizado?: boolean;
};

/** Cartão flutuante que repete, em letra grande, o que a tela do celular mostra. */
export const Chamada: React.FC<Props> = ({ titulo, texto, cor, progresso, esquerda = 80, topo, largura = 640, centralizado = false }) => (
  <div
    style={{
      position: 'absolute',
      left: esquerda,
      top: topo,
      width: largura,
      padding: '24px 28px',
      textAlign: centralizado ? 'center' : 'left',
      borderRadius: 30,
      backgroundColor: comTransparencia(cores.superficie, 0.96),
      border: `3px solid ${cor}`,
      boxShadow: `0 30px 60px rgba(0, 0, 0, 0.55), 0 0 40px ${comTransparencia(cor, 0.35)}`,
      opacity: progresso,
      transform: `translateY(${(1 - progresso) * 60}px) scale(${0.9 + 0.1 * progresso})`,
      transformOrigin: centralizado ? 'center' : 'left center',
    }}
  >
    {titulo && <div style={{ fontFamily: fonteTitulo, fontSize: 72, lineHeight: 1, color: cor, marginBottom: 12 }}>{titulo}</div>}
    <div style={{ fontFamily: fonteTexto, fontWeight: 800, fontSize: 56, lineHeight: 1.12, color: cores.texto }}>{texto}</div>
  </div>
);
