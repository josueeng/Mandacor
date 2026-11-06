import { interpolate } from 'remotion';

const rgb = (hex: string) => {
  const valor = parseInt(hex.replace('#', ''), 16);
  return [(valor >> 16) & 255, (valor >> 8) & 255, valor & 255];
};

/** Mistura duas cores hexadecimais; t = 0 devolve a, t = 1 devolve b. */
export function misturar(a: string, b: string, t: number): string {
  const [r1, g1, b1] = rgb(a);
  const [r2, g2, b2] = rgb(b);
  const canal = (x: number, y: number) => Math.round(x + (y - x) * t);
  return `rgb(${canal(r1, r2)}, ${canal(g1, g2)}, ${canal(b1, b2)})`;
}

export const comTransparencia = (hex: string, alfa: number) => {
  const [r, g, b] = rgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alfa})`;
};

/** interpolate com os extremos travados, que é o caso de quase todas as animações aqui. */
export const faixa = (frame: number, entrada: number[], saida: number[]) =>
  interpolate(frame, entrada, saida, { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
