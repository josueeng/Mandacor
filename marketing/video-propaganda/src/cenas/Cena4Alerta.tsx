import React from 'react';
import { AbsoluteFill, Html5Audio, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { Celular } from '../componentes/Celular';
import { Chamada } from '../componentes/Chamada';
import { Etiqueta } from '../componentes/Marca';
import { TelaApp } from '../componentes/TelaApp';
import { Titulo } from '../componentes/Titulo';
import { config, cores } from '../config';
import { faixa } from '../util';

const QUADRO_ALERTA = 3;

/** Cena 4: a tela troca para "FICOU PIOR", com tremida e brilho vermelho. */
export const Cena4Alerta: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const textos = config.textos[4];
  const desde = frame - QUADRO_ALERTA;
  const tremida = desde >= 0 ? Math.sin(desde * 2.1) * 16 * Math.exp(-desde / 9) : 0;
  const brilho = faixa(frame, [0, 6, 40], [0, 1, 0.65]) * (0.85 + 0.15 * Math.sin(frame / 5));
  const clarao = faixa(frame, [QUADRO_ALERTA, QUADRO_ALERTA + 3, QUADRO_ALERTA + 18], [0, 0.22, 0]);
  const entradaChamada = spring({ frame: frame - 12, fps, config: { damping: 14 } });

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{ background: `radial-gradient(900px 900px at 70% 55%, rgba(255, 102, 107, ${clarao}), transparent 70%)` }}
      />
      <Etiqueta />
      <Titulo texto={textos.titulo} destaque={textos.destaque} corDestaque={cores.perigo} />
      <Celular deslocamentoX={tremida} corBrilho={cores.perigo} forcaBrilho={0.55 * brilho}>
        <TelaApp tipo="ficou_pior" />
      </Celular>
      <Chamada titulo={textos.alerta} texto={textos.detalhe} cor={cores.perigo} progresso={entradaChamada} topo={1100} largura={700} />
      <Sequence from={QUADRO_ALERTA} durationInFrames={20}>
        <Html5Audio src={staticFile('sfx/alerta.wav')} volume={config.volumes.efeitos} />
      </Sequence>
    </AbsoluteFill>
  );
};
