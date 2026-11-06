import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

/**
 * Fontes embutidas em public/fontes (licença OFL), para o render funcionar sem internet
 * e sair igual em qualquer computador.
 */
const ARQUIVOS: Array<{ familia: string; peso: string; arquivo: string }> = [
  { familia: 'Archivo Black', peso: '400', arquivo: 'archivo-black-latin-400-normal.woff2' },
  { familia: 'Inter', peso: '500', arquivo: 'inter-latin-500-normal.woff2' },
  { familia: 'Inter', peso: '700', arquivo: 'inter-latin-700-normal.woff2' },
  { familia: 'Inter', peso: '800', arquivo: 'inter-latin-800-normal.woff2' },
  { familia: 'Inter', peso: '900', arquivo: 'inter-latin-900-normal.woff2' },
  { familia: 'Space Mono', peso: '400', arquivo: 'space-mono-latin-400-normal.woff2' },
  { familia: 'Space Mono', peso: '700', arquivo: 'space-mono-latin-700-normal.woff2' },
];

for (const { familia, peso, arquivo } of ARQUIVOS) {
  loadFont({ family: familia, weight: peso, url: staticFile(`fontes/${arquivo}`) });
}

export const fonteTitulo = '"Archivo Black", "Arial Black", sans-serif';
export const fonteTexto = 'Inter, Arial, sans-serif';
export const fonteNumeros = '"Space Mono", "Courier New", monospace';
