import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

import { PontosMarca } from '../componentes/Marca';
import { config, cores } from '../config';
import { fonteNumeros, fonteTexto, fonteTitulo } from '../fontes';
import { comTransparencia } from '../util';

/** Cena 6: marca, promessa e chamada para a demonstração. */
export const Cena6Fechamento: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const textos = config.textos[6];
  const pontos = [0, 1, 2, 3, 4].map((i) => spring({ frame: frame - 2 - i * 4, fps, config: { damping: 11 } }));
  const marca = spring({ frame: frame - 10, fps, config: { damping: 14 } });
  const subtitulo = spring({ frame: frame - 20, fps, config: { damping: 200 } });
  const cartao = spring({ frame: frame - 30, fps, config: { damping: 15 } });
  const pulso = 0.5 + 0.5 * Math.sin(frame / 8);

  return (
    <AbsoluteFill style={{ alignItems: 'center' }}>
      <div style={{ position: 'absolute', top: 330 }}>
        <PontosMarca tamanho={260} progresso={pontos} />
      </div>
      <div
        style={{
          position: 'absolute',
          top: 520,
          fontFamily: fonteTitulo,
          fontSize: 134,
          letterSpacing: 1,
          color: cores.texto,
          opacity: marca,
          transform: `scale(${0.85 + 0.15 * marca})`,
        }}
      >
        {textos.marca}
      </div>
      <div
        style={{
          position: 'absolute',
          top: 730,
          left: 80,
          right: 80,
          textAlign: 'center',
          fontFamily: fonteTexto,
          fontWeight: 800,
          fontSize: 64,
          lineHeight: 1.15,
          color: cores.textoSecundario,
          opacity: subtitulo,
          transform: `translateY(${(1 - subtitulo) * 30}px)`,
        }}
      >
        {textos.subtitulo}
      </div>
      <div
        style={{
          position: 'absolute',
          top: 950,
          left: 80,
          right: 80,
          padding: '30px 36px',
          borderRadius: 34,
          textAlign: 'center',
          backgroundColor: cores.superficie,
          border: `3px solid ${cores.tecnico}`,
          boxShadow: `0 0 ${30 + 30 * pulso}px ${comTransparencia(cores.tecnico, 0.35)}`,
          opacity: cartao,
          transform: `translateY(${(1 - cartao) * 80}px)`,
        }}
      >
        <div style={{ fontFamily: fonteTexto, fontWeight: 800, fontSize: 56, lineHeight: 1.15, color: cores.texto }}>
          {textos.cartao}
        </div>
        <div style={{ marginTop: 18, fontFamily: fonteNumeros, fontWeight: 700, fontSize: 64, color: cores.sucesso }}>
          {config.whatsapp}
        </div>
      </div>
    </AbsoluteFill>
  );
};
