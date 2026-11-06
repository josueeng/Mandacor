import { getStaticFiles, staticFile } from 'remotion';

/** Verdadeiro quando o arquivo existe em public/ (nome relativo, ex.: "voz/cena-1.mp3"). */
export const existe = (nome: string): boolean => getStaticFiles().some((arquivo) => arquivo.name === nome);

export const arquivoSeExistir = (nome: string): string | null => (existe(nome) ? staticFile(nome) : null);
