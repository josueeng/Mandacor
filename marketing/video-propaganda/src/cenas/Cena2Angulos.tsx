import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

import { ANGULOS, CORES_ANGULO, Etiqueta } from '../componentes/Marca';
import { Chapinha } from '../componentes/Objetos';
import { Titulo } from '../componentes/Titulo';
import { config, cores } from '../config';
import { fonteNumeros } from '../fontes';
import { comTransparencia, faixa, misturar } from '../util';

const CENTRO = { x: 540, y: 1230 };
const RAIO = 400;

/** Cena 2: a chapinha gira e cada ângulo mostra uma cor diferente. */
export const Cena2Angulos: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const textos = config.textos[2];
  const giro = 30 * Math.sin(frame / 16 - 1.2);
  // Inclinação da chapinha -> posição entre 15° (0) e 105° (4).
  const posicao = faixa(giro, [-30, 30], [0, 4]);
  const base = Math.floor(Math.min(posicao, 3.999));
  const cor = misturar(CORES_ANGULO[base], CORES_ANGULO[base + 1], posicao - base);
  const ativo = Math.round(posicao);
  const entrada = spring({ frame: frame - 2, fps, config: { damping: 16 } });

  return (
    <AbsoluteFill>
      <Etiqueta />
      <Titulo texto={textos.titulo} destaque={textos.destaque} corDestaque={cores.tecnico} />
      <div
        style={{
          position: 'absolute',
          left: CENTRO.x - 170,
          top: 940,
          opacity: entrada,
          transform: `translateY(${(1 - entrada) * 120}px)`,
        }}
      >
        <Chapinha largura={340} altura={440} cor={cor} rotacaoY={giro} reflexo={faixa(giro, [-30, 30], [0.15, 0.85])} />
      </div>
      {ANGULOS.map((angulo, i) => {
        const theta = Math.PI * ((160 - i * 35) / 180);
        const x = CENTRO.x + RAIO * Math.cos(theta);
        const y = CENTRO.y - RAIO * Math.sin(theta);
        const aparece = spring({ frame: frame - 8 - i * 6, fps, config: { damping: 14 } });
        const destacado = frame > 36 && i === ativo;
        return (
          <div
            key={angulo}
            style={{
              position: 'absolute',
              left: x - 100,
              top: y - 44,
              width: 200,
              height: 88,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 14,
              borderRadius: 44,
              backgroundColor: cores.superficie,
              border: `3px solid ${destacado ? cores.tecnico : cores.borda}`,
              boxShadow: destacado ? `0 0 34px ${comTransparencia(cores.tecnico, 0.6)}` : 'none',
              opacity: aparece,
              transform: `scale(${(0.5 + 0.5 * aparece) * (destacado ? 1.08 : 1)})`,
              fontFamily: fonteNumeros,
              fontWeight: 700,
              fontSize: 48,
              color: cores.texto,
            }}
          >
            <span
              style={{
                width: 40,
                height: 40,
                borderRadius: 20,
                backgroundColor: CORES_ANGULO[i],
                border: '2px solid rgba(255, 255, 255, 0.35)',
              }}
            />
            {angulo}°
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
