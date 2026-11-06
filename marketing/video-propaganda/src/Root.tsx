import React from 'react';
import { Composition } from 'remotion';

import { calcularMetadados, FPS } from './metadados';
import { PropsVideo } from './tipos';
import { Video } from './Video';

const propsIniciais = (versao: PropsVideo['versao']): PropsVideo => ({
  versao,
  cenas: [],
  musica: null,
  destaqueResultados: null,
});

/** Duas versões: completa (~30 s, cenas 1–6) e curta (~15 s, cenas 1, 3, 4, 5 e 6). */
export const Raiz: React.FC = () => (
  <>
    <Composition
      id="Completa"
      component={Video}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={30 * FPS}
      defaultProps={propsIniciais('completa')}
      calculateMetadata={calcularMetadados}
    />
    <Composition
      id="Curta"
      component={Video}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={15 * FPS}
      defaultProps={propsIniciais('curta')}
      calculateMetadata={calcularMetadados}
    />
  </>
);
