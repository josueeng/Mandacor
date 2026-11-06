import { VERSOES } from './config';

export type Versao = keyof typeof VERSOES;
export type CenaId = 1 | 2 | 3 | 4 | 5 | 6;

export type Palavra = { texto: string; inicio: number; fim: number };

export type Retangulo = { x: number; y: number; w: number; h: number };

export type CenaCalculada = {
  id: CenaId;
  /** Frame em que a cena começa no vídeo (já descontando as transições). */
  inicio: number;
  duracao: number;
  voz: string | null;
  vozSegundos: number;
  texto: string;
  palavras: Palavra[] | null;
};

export type PropsVideo = {
  versao: Versao;
  cenas: CenaCalculada[];
  musica: string | null;
  /** Linha a destacar no print da tela de Resultados, em pixels da tela de 412 px. */
  destaqueResultados: Retangulo | null;
};
