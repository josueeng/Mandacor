import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

import { Etiqueta } from '../componentes/Marca';
import { Chapinha, Olho, PortaCarro } from '../componentes/Objetos';
import { Titulo } from '../componentes/Titulo';
import { config, cores } from '../config';
import { fonteNumeros, fonteTitulo } from '../fontes';
import { faixa } from '../util';

/** Cena 1: a dor de acertar a cor no olho. */
export const Cena1Dor: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const textos = config.textos[1];
  const entradaChapinha = spring({ frame: frame - 4, fps, config: { damping: 18, mass: 0.8 } });
  const entradaPorta = spring({ frame: frame - 9, fps, config: { damping: 18, mass: 0.8 } });
  const entradaOlho = spring({ frame: frame - 12, fps, config: { damping: 12 } });
  const diferente = spring({ frame: frame - 24, fps, config: { damping: 10 } });
  // O olho pisca uma vez, como quem compara a cor de novo.
  const abertura = faixa(frame, [44, 48, 52], [1, 0.1, 1]);
  const pulsoInterrogacao = 1 + 0.09 * Math.sin(frame / 4);

  return (
    <AbsoluteFill>
      <Etiqueta />
      <Titulo texto={textos.titulo} destaque={textos.destaque} corDestaque={cores.perigo} />
      <div
        style={{
          position: 'absolute',
          left: 300,
          top: 560,
          width: 480,
          height: 220,
          opacity: entradaOlho,
          transform: `scale(${0.6 + 0.4 * entradaOlho})`,
        }}
      >
        <div style={{ position: 'absolute', left: 0, top: 40 }}>
          <Olho largura={250} abertura={abertura} />
        </div>
        <div
          style={{
            position: 'absolute',
            left: 300,
            top: -20,
            fontFamily: fonteTitulo,
            fontSize: 190,
            lineHeight: 1,
            color: cores.alerta,
            transform: `scale(${pulsoInterrogacao})`,
          }}
        >
          ?
        </div>
      </div>
      <div style={{ position: 'absolute', left: 90, top: 805, transform: `translateX(${(1 - entradaChapinha) * -560}px)` }}>
        <Chapinha largura={340} altura={460} cor="#8FA3BA" rotacao={-4} reflexo={0.3 + 0.08 * Math.sin(frame / 18)} />
        <Rotulo texto="CHAPINHA" />
      </div>
      <div style={{ position: 'absolute', left: 530, top: 790, transform: `translateX(${(1 - entradaPorta) * 620}px)` }}>
        <PortaCarro largura={430} cor="#6E8CB6" />
        <Rotulo texto="CARRO" />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 440,
          top: 950,
          fontFamily: fonteTitulo,
          fontSize: 150,
          lineHeight: 1,
          color: cores.perigo,
          opacity: diferente,
          transform: `scale(${0.4 + 0.6 * diferente})`,
          textShadow: '0 6px 30px rgba(0, 0, 0, 0.8)',
        }}
      >
        ≠
      </div>
    </AbsoluteFill>
  );
};

const Rotulo: React.FC<{ texto: string }> = ({ texto }) => (
  <div
    style={{
      marginTop: 18,
      textAlign: 'center',
      fontFamily: fonteNumeros,
      fontWeight: 700,
      fontSize: 34,
      letterSpacing: 5,
      color: cores.textoSecundario,
    }}
  >
    {texto}
  </div>
);
