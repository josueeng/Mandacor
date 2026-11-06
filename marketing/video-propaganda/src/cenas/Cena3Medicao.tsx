import React from 'react';
import { AbsoluteFill, Html5Audio, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { Celular, ESCALA_TELA, ORIGEM_TELA } from '../componentes/Celular';
import { Chamada } from '../componentes/Chamada';
import { Etiqueta } from '../componentes/Marca';
import { Espectrofotometro } from '../componentes/Objetos';
import { TelaApp } from '../componentes/TelaApp';
import { Titulo } from '../componentes/Titulo';
import { config, cores } from '../config';
import { Retangulo } from '../tipos';
import { faixa } from '../util';

const QUADRO_CLIQUE = 19;
/** A faixa termina acima da legenda mais alta (3 linhas), que começa perto de y = 1340. */
const TOPO_FAIXA = 1180;

/** Cena 3: o espectrofotômetro lê e o app explica a diferença. */
export const Cena3Medicao: React.FC<{ destaque: Retangulo | null }> = ({ destaque }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const textos = config.textos[3];
  const entradaAparelho = spring({ frame, fps, config: { damping: 16 } });
  const leitura = faixa(frame, [6, 14, 30], [0, 1, 0.35]) + 0.15 * Math.max(0, Math.sin(frame / 5));
  const entradaCelular = spring({ frame: frame - 9, fps, config: { damping: 16, mass: 0.9 } });
  const progressoDestaque = spring({ frame: frame - 30, fps, config: { damping: 14 } });
  const entradaChamada = spring({ frame: frame - 38, fps, config: { damping: 15 } });
  // Ondas de sinal saindo do aparelho em direção ao celular.
  const ondas = [0, 1, 2].map((i) => {
    const ciclo = ((frame - 12 - i * 6) % 24) / 24;
    return frame < 12 + i * 6 ? 0 : Math.sin(Math.PI * ciclo);
  });
  // A linha destacada no print, em coordenadas do vídeo, para ligar o cartão a ela.
  const yLinha = destaque ? ORIGEM_TELA.y + (destaque.y + destaque.h + 6) * ESCALA_TELA : TOPO_FAIXA - 20;

  return (
    <AbsoluteFill>
      <Etiqueta />
      <Titulo texto={textos.titulo} destaque={textos.destaque} corDestaque={cores.tecnico} />
      <div style={{ position: 'absolute', left: 80, top: 830, transform: `translateX(${(1 - entradaAparelho) * -420}px)` }}>
        <Espectrofotometro largura={210} leitura={leitura} />
      </div>
      {ondas.map((forca, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            left: 300 + i * 52,
            top: 930 - i * 18,
            width: 70 + i * 36,
            height: 120 + i * 36,
            borderRadius: '50%',
            border: `6px solid ${cores.tecnico}`,
            borderLeftColor: 'transparent',
            borderBottomColor: 'transparent',
            transform: 'rotate(45deg)',
            opacity: forca * 0.8,
          }}
        />
      ))}
      <Celular deslocamentoX={(1 - entradaCelular) * 640} forcaBrilho={0.35 * entradaCelular}>
        <TelaApp tipo="resultados" destaque={destaque} progressoDestaque={progressoDestaque} />
      </Celular>
      <div
        style={{
          position: 'absolute',
          left: 760,
          top: yLinha,
          width: 4,
          height: Math.max(0, TOPO_FAIXA - yLinha),
          backgroundColor: cores.tecnico,
          opacity: entradaChamada,
        }}
      />
      <Chamada texto={textos.frase} cor={cores.tecnico} progresso={entradaChamada} topo={TOPO_FAIXA} largura={920} centralizado />
      <Sequence from={QUADRO_CLIQUE} durationInFrames={10}>
        <Html5Audio src={staticFile('sfx/clique.wav')} volume={config.volumes.efeitos} />
      </Sequence>
    </AbsoluteFill>
  );
};
