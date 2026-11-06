import { fade } from '@remotion/transitions/fade';
import { linearTiming, TransitionSeries } from '@remotion/transitions';
import React from 'react';
import { AbsoluteFill, Html5Audio, Sequence, staticFile, useVideoConfig } from 'remotion';

import { Cena1Dor } from './cenas/Cena1Dor';
import { Cena2Angulos } from './cenas/Cena2Angulos';
import { Cena3Medicao } from './cenas/Cena3Medicao';
import { Cena4Alerta } from './cenas/Cena4Alerta';
import { Cena5Acerto } from './cenas/Cena5Acerto';
import { Cena6Fechamento } from './cenas/Cena6Fechamento';
import { Fundo } from './componentes/Fundo';
import { Legenda } from './componentes/Legenda';
import { config } from './config';
import { CenaCalculada, PropsVideo, Retangulo } from './tipos';
import { faixa } from './util';

/** O whoosh começa um pouco antes da transição para o pico cair no meio dela. */
const ANTECIPA_WHOOSH = 2;
const RAMPA_DUCKING = 8;

const ConteudoDaCena: React.FC<{ cena: CenaCalculada; destaque: Retangulo | null }> = ({ cena, destaque }) => {
  switch (cena.id) {
    case 1:
      return <Cena1Dor />;
    case 2:
      return <Cena2Angulos />;
    case 3:
      return <Cena3Medicao destaque={destaque} />;
    case 4:
      return <Cena4Alerta />;
    case 5:
      return <Cena5Acerto />;
    case 6:
      return <Cena6Fechamento />;
  }
};

/** Volume da música: abaixa durante a fala e tem fade-in e fade-out. */
function volumeDaMusica(frame: number, cenas: CenaCalculada[], total: number, fps: number): number {
  const { musica, musicaDuranteFala } = config.volumes;
  let abaixamento = 0;
  for (const cena of cenas) {
    if (!cena.voz) continue;
    // Com os tempos das palavras, a música só abaixa entre a primeira e a última palavra.
    const primeira = cena.palavras?.[0]?.inicio ?? 0;
    const ultima = cena.palavras?.[cena.palavras.length - 1]?.fim ?? cena.vozSegundos;
    const inicio = cena.inicio + Math.floor(primeira * fps);
    const fim = cena.inicio + Math.ceil(ultima * fps);
    abaixamento = Math.max(
      abaixamento,
      faixa(frame, [inicio - RAMPA_DUCKING, inicio, fim, fim + RAMPA_DUCKING], [0, 1, 1, 0]),
    );
  }
  const base = musica - (musica - musicaDuranteFala) * abaixamento;
  const entrada = faixa(frame, [0, fps], [0, 1]);
  const saida = faixa(frame, [total - 1.5 * fps, total], [1, 0]);
  return base * entrada * saida;
}

export const Video: React.FC<PropsVideo> = ({ cenas, musica, destaqueResultados }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const transicao = config.transicaoFrames;

  const trilha: React.ReactNode[] = [];
  cenas.forEach((cena, i) => {
    if (i > 0) {
      trilha.push(
        <TransitionSeries.Transition
          key={`transicao-${cena.id}`}
          presentation={fade()}
          timing={linearTiming({ durationInFrames: transicao })}
        />,
      );
    }
    trilha.push(
      <TransitionSeries.Sequence key={`cena-${cena.id}`} durationInFrames={cena.duracao}>
        <ConteudoDaCena cena={cena} destaque={destaqueResultados} />
        <Legenda texto={cena.texto} palavras={cena.palavras} segundos={cena.vozSegundos} />
      </TransitionSeries.Sequence>,
    );
  });

  return (
    <AbsoluteFill>
      <Fundo />
      <TransitionSeries>{trilha}</TransitionSeries>
      {cenas.map(
        (cena) =>
          cena.voz && (
            <Sequence key={`voz-${cena.id}`} from={cena.inicio} durationInFrames={cena.duracao}>
              <Html5Audio src={cena.voz} volume={config.volumes.voz} />
            </Sequence>
          ),
      )}
      {cenas.slice(1).map((cena) => (
        <Sequence key={`whoosh-${cena.id}`} from={Math.max(0, cena.inicio - ANTECIPA_WHOOSH)} durationInFrames={18}>
          <Html5Audio src={staticFile('sfx/whoosh.wav')} volume={config.volumes.efeitos} />
        </Sequence>
      ))}
      {musica && (
        <Html5Audio
          src={musica}
          loop
          loopVolumeCurveBehavior="extend"
          volume={(frame) => volumeDaMusica(frame, cenas, durationInFrames, fps)}
        />
      )}
    </AbsoluteFill>
  );
};
