import React from 'react';

import { cores } from '../config';
import { fonteNumeros } from '../fontes';

/** Cores de uma chapinha metálica vista de 15° (mais clara) a 105° (mais escura). */
export const CORES_ANGULO = ['#DCE6F1', '#BCCADB', '#93A7BD', '#64778F', '#4C5C72'];
export const ANGULOS = [15, 25, 45, 75, 105];

/** Símbolo da marca: cinco pontos em arco, um para cada ângulo de leitura. */
export const PontosMarca: React.FC<{ tamanho: number; progresso?: number[] }> = ({ tamanho, progresso }) => {
  const raio = tamanho * 0.42;
  return (
    <svg width={tamanho} height={tamanho * 0.62} viewBox={`0 0 ${tamanho} ${tamanho * 0.62}`}>
      {ANGULOS.map((_, i) => {
        const angulo = Math.PI * (0.92 - i * 0.21);
        const x = tamanho / 2 + raio * Math.cos(angulo);
        const y = tamanho * 0.56 - raio * Math.sin(angulo);
        const p = progresso?.[i] ?? 1;
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={tamanho * 0.075 * p}
            fill={i === 2 ? cores.tecnico : CORES_ANGULO[i]}
            opacity={p}
          />
        );
      })}
    </svg>
  );
};

/** Etiqueta "MANDACOR" no topo das cenas. */
export const Etiqueta: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      top: 118,
      left: 80,
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      fontFamily: fonteNumeros,
      fontWeight: 700,
      fontSize: 32,
      letterSpacing: 6,
      color: cores.textoSecundario,
    }}
  >
    <PontosMarca tamanho={58} />
    MANDACOR
  </div>
);
