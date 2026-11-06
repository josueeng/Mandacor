import React from 'react';
import { AbsoluteFill, Html5Audio, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import { Celular } from '../componentes/Celular';
import { Chamada } from '../componentes/Chamada';
import { Etiqueta } from '../componentes/Marca';
import { TelaApp } from '../componentes/TelaApp';
import { Titulo } from '../componentes/Titulo';
import { config, cores } from '../config';
import { fonteNumeros, fonteTexto } from '../fontes';
import { comTransparencia, faixa } from '../util';

const QUADRO_SUCESSO = 3;

/** Histórico ilustrativo: o ajuste que piorou e o que acertou a cor ficam registrados. */
const HISTORICO = [
  { rotulo: 'AJUSTE 3', status: 'MELHOROU', cor: cores.sucesso },
  { rotulo: 'AJUSTE 2', status: 'FICOU PIOR', cor: cores.perigo },
  { rotulo: 'AJUSTE 1', status: 'SEM MUDANÇA', cor: cores.tecnico },
];

/** Cena 5: a nova leitura mostra "MELHOROU" e o ajuste entra no histórico. */
export const Cena5Acerto: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const textos = config.textos[5];
  const brilho = faixa(frame, [0, 6, 40], [0, 1, 0.7]) * (0.85 + 0.15 * Math.sin(frame / 6));
  const entradaChamada = spring({ frame: frame - 30, fps, config: { damping: 14 } });

  return (
    <AbsoluteFill>
      <Etiqueta />
      <Titulo texto={textos.titulo} destaque={textos.destaque} corDestaque={cores.sucesso} />
      <Celular corBrilho={cores.sucesso} forcaBrilho={0.55 * brilho}>
        <TelaApp tipo="melhorou" />
      </Celular>
      {HISTORICO.map((item, i) => {
        const entrada = spring({ frame: frame - 8 - i * 7, fps, config: { damping: 15 } });
        const novo = i === 0;
        return (
          <div
            key={item.rotulo}
            style={{
              position: 'absolute',
              left: 80,
              top: 600 + i * 140,
              width: 470,
              height: 124,
              padding: '14px 26px',
              boxSizing: 'border-box',
              borderRadius: 24,
              backgroundColor: cores.superficie,
              border: `2px solid ${novo ? item.cor : cores.borda}`,
              borderLeft: `10px solid ${item.cor}`,
              boxShadow: novo ? `0 0 36px ${comTransparencia(item.cor, 0.4)}` : 'none',
              opacity: entrada * (novo ? 1 : 0.8),
              transform: `translateX(${(1 - entrada) * -300}px)`,
            }}
          >
            <div style={{ fontFamily: fonteNumeros, fontWeight: 700, fontSize: 28, letterSpacing: 4, color: cores.textoSecundario }}>
              {item.rotulo}
            </div>
            <div style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 50, lineHeight: 1.05, color: item.cor }}>{item.status}</div>
          </div>
        );
      })}
      <Chamada titulo={textos.resultado} texto={textos.detalhe} cor={cores.sucesso} progresso={entradaChamada} topo={1100} largura={700} />
      <Sequence from={QUADRO_SUCESSO} durationInFrames={24}>
        <Html5Audio src={staticFile('sfx/sucesso.wav')} volume={config.volumes.efeitos} />
      </Sequence>
    </AbsoluteFill>
  );
};
