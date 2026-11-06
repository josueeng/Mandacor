import React from 'react';

import { cores } from '../config';
import { misturar } from '../util';

type PropsChapinha = {
  largura: number;
  altura: number;
  cor: string;
  /** Posição do reflexo, de 0 (esquerda) a 1 (direita). */
  reflexo?: number;
  rotacaoY?: number;
  rotacao?: number;
};

/** Chapinha de teste pintada com tinta metálica. */
export const Chapinha: React.FC<PropsChapinha> = ({ largura, altura, cor, reflexo = 0.35, rotacaoY = 0, rotacao = 0 }) => {
  const claro = misturar(cor, '#FFFFFF', 0.35);
  const escuro = misturar(cor, '#05070A', 0.45);
  const p = reflexo * 100;
  return (
    <div style={{ perspective: 1600, width: largura, height: altura }}>
      <div
        style={{
          position: 'relative',
          width: largura,
          height: altura,
          borderRadius: 26,
          overflow: 'hidden',
          background: `linear-gradient(160deg, ${claro} 0%, ${cor} 46%, ${escuro} 100%)`,
          border: '2px solid rgba(255, 255, 255, 0.22)',
          boxShadow: '0 34px 70px rgba(0, 0, 0, 0.6)',
          transform: `rotateY(${rotacaoY}deg) rotate(${rotacao}deg)`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: `linear-gradient(112deg, transparent ${p - 20}%, rgba(255, 255, 255, 0.55) ${p}%, transparent ${p + 20}%)`,
          }}
        />
        {/* partículas de alumínio */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.5) 1.1px, transparent 1.6px)',
            backgroundSize: '9px 9px',
            opacity: 0.22,
          }}
        />
        {/* furo de pendurar a chapinha */}
        <div
          style={{
            position: 'absolute',
            top: 22,
            left: '50%',
            width: 28,
            height: 28,
            marginLeft: -14,
            borderRadius: 14,
            backgroundColor: cores.fundo,
            boxShadow: 'inset 0 3px 6px rgba(0, 0, 0, 0.8), 0 1px 0 rgba(255, 255, 255, 0.35)',
          }}
        />
      </div>
    </div>
  );
};

/** Porta de carro estilizada, pintada numa cor um pouco diferente da chapinha. */
export const PortaCarro: React.FC<{ largura: number; cor: string }> = ({ largura, cor }) => {
  const altura = (largura * 560) / 470;
  return (
    <svg width={largura} height={altura} viewBox="0 0 470 560">
      <defs>
        <linearGradient id="lataria" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={misturar(cor, '#FFFFFF', 0.3)} />
          <stop offset="55%" stopColor={cor} />
          <stop offset="100%" stopColor={misturar(cor, '#05070A', 0.5)} />
        </linearGradient>
        <linearGradient id="vidro" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2B3F55" />
          <stop offset="100%" stopColor="#0B1119" />
        </linearGradient>
      </defs>
      <path
        d="M 30 250 L 120 70 Q 135 40 170 40 L 440 40 Q 460 40 460 62 L 460 530 Q 460 550 440 550 L 52 550 Q 30 550 30 528 Z"
        fill="url(#lataria)"
        stroke="rgba(255,255,255,0.25)"
        strokeWidth={3}
      />
      <path d="M 82 236 L 152 92 Q 160 78 178 78 L 424 78 Q 432 78 432 88 L 432 236 Z" fill="url(#vidro)" />
      <path d="M 210 236 L 300 78 L 350 78 L 260 236 Z" fill="rgba(255,255,255,0.08)" />
      <path d="M 36 330 Q 250 316 460 322" stroke="rgba(255,255,255,0.3)" strokeWidth={3} fill="none" />
      <rect x={330} y={360} width={92} height={24} rx={12} fill={misturar(cor, '#05070A', 0.55)} />
      <rect x={336} y={364} width={80} height={6} rx={3} fill="rgba(255,255,255,0.35)" />
    </svg>
  );
};

/** Olho estilizado; abertura 1 = aberto, 0 = fechado. */
export const Olho: React.FC<{ largura: number; abertura?: number }> = ({ largura, abertura = 1 }) => (
  <svg width={largura} height={(largura * 140) / 240} viewBox="0 0 240 140">
    <g transform={`translate(0 ${70 * (1 - abertura)}) scale(1 ${Math.max(0.05, abertura)})`}>
      <path d="M 10 70 Q 120 -14 230 70 Q 120 154 10 70 Z" fill={cores.superficie} stroke={cores.texto} strokeWidth={8} />
      <circle cx={120} cy={70} r={36} fill={cores.tecnico} />
      <circle cx={120} cy={70} r={16} fill={cores.fundo} />
      <circle cx={132} cy={58} r={7} fill="#FFFFFF" />
    </g>
  </svg>
);

/** Espectrofotômetro genérico (sem marca), com a abertura de leitura que pisca. */
export const Espectrofotometro: React.FC<{ largura: number; leitura?: number; barras?: number[] }> = ({
  largura,
  leitura = 0,
  barras = [0.9, 0.75, 0.55, 0.35, 0.25],
}) => (
  <svg width={largura} height={(largura * 460) / 300} viewBox="0 0 300 460">
    <defs>
      <linearGradient id="corpo" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#3A4755" />
        <stop offset="40%" stopColor="#1A2129" />
        <stop offset="100%" stopColor="#0C1015" />
      </linearGradient>
      <radialGradient id="luz">
        <stop offset="0%" stopColor={cores.tecnico} stopOpacity={0.9} />
        <stop offset="100%" stopColor={cores.tecnico} stopOpacity={0} />
      </radialGradient>
    </defs>
    {/* corpo e empunhadura */}
    <path
      d="M 40 20 Q 40 0 62 0 L 238 0 Q 260 0 260 20 L 260 250 Q 260 268 246 280 L 214 312 L 214 360 L 86 360 L 86 312 L 54 280 Q 40 268 40 250 Z"
      fill="url(#corpo)"
      stroke="#4A5766"
      strokeWidth={3}
    />
    {/* visor com as barras dos 5 ângulos */}
    <rect x={64} y={28} width={172} height={120} rx={14} fill="#05080C" stroke={cores.borda} strokeWidth={2} />
    {barras.map((valor, i) => (
      <rect
        key={i}
        x={84 + i * 30}
        y={136 - 90 * valor}
        width={18}
        height={90 * valor}
        rx={4}
        fill={i === 2 ? cores.tecnico : '#5C7A99'}
      />
    ))}
    {/* botões */}
    <circle cx={110} cy={196} r={16} fill="#232C36" stroke="#3A4755" strokeWidth={2} />
    <circle cx={150} cy={210} r={22} fill={cores.acao} opacity={0.9} />
    <circle cx={190} cy={196} r={16} fill="#232C36" stroke="#3A4755" strokeWidth={2} />
    {/* cabeça de medição */}
    <rect x={70} y={360} width={160} height={70} rx={20} fill="#10151B" stroke="#4A5766" strokeWidth={3} />
    <ellipse cx={150} cy={432} rx={56} ry={14} fill="#05070A" />
    <ellipse cx={150} cy={432} rx={36 + 40 * leitura} ry={9 + 10 * leitura} fill="url(#luz)" opacity={leitura} />
    <ellipse cx={150} cy={432} rx={36} ry={9} fill="none" stroke={cores.tecnico} strokeWidth={3} opacity={0.4 + 0.6 * leitura} />
  </svg>
);
