import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';

import { cores } from '../config';

/** Fundo escuro da bancada: brilho azul suave e uma grade técnica que some para baixo. */
export const Fundo: React.FC = () => {
  const frame = useCurrentFrame();
  const deriva = Math.sin(frame / 90) * 6;
  return (
    <AbsoluteFill style={{ backgroundColor: cores.fundo }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(1000px 760px at ${78 + deriva}% 6%, rgba(73, 174, 248, 0.17), transparent 70%),
            radial-gradient(900px 900px at 8% 96%, rgba(228, 71, 77, 0.07), transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            'linear-gradient(rgba(58, 71, 85, 0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(58, 71, 85, 0.5) 1px, transparent 1px)',
          backgroundSize: '90px 90px',
          backgroundPosition: '0 30px',
          opacity: 0.22,
          maskImage: 'linear-gradient(to bottom, black 0%, transparent 80%)',
        }}
      />
    </AbsoluteFill>
  );
};
