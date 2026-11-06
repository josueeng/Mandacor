import { getAudioDurationInSeconds } from '@remotion/media-utils';
import { CalculateMetadataFunction, staticFile } from 'remotion';

import { arquivoSeExistir, existe } from './arquivos';
import { config, VERSOES } from './config';
import { CenaCalculada, CenaId, Palavra, PropsVideo, Retangulo } from './tipos';

export const FPS = 30;

/** Sem arquivo de voz, a cena ainda ganha uma duração plausível pelo tamanho do texto. */
const estimarSegundos = (texto: string) => Math.max(1.5, texto.length / 14);

async function lerJson<T>(nome: string): Promise<T | null> {
  if (!existe(nome)) return null;
  const resposta = await fetch(staticFile(nome));
  return resposta.ok ? ((await resposta.json()) as T) : null;
}

export const calcularMetadados: CalculateMetadataFunction<PropsVideo> = async ({ props }) => {
  const versao = VERSOES[props.versao];
  const textos = config.narracao[props.versao] as Record<string, string>;
  const transicao = config.transicaoFrames;
  const cenas: CenaCalculada[] = [];
  let cursor = 0;

  for (const [indice, id] of versao.cenas.entries()) {
    const texto = textos[String(id)];
    const nomeVoz = `${versao.prefixoVoz}${id}.mp3`;
    const voz = arquivoSeExistir(nomeVoz);
    const vozSegundos = voz ? await getAudioDurationInSeconds(voz) : estimarSegundos(texto);
    const tempos = voz ? await lerJson<{ texto: string; palavras: Palavra[] }>(nomeVoz.replace('.mp3', '.json')) : null;
    // Os tempos das palavras só valem se o áudio foi gerado a partir do texto atual.
    const palavras = tempos && tempos.texto === texto ? tempos.palavras : null;

    const ultima = indice === versao.cenas.length - 1;
    const segundos = vozSegundos + config.respiroSegundos + (ultima ? config.seguraFinalSegundos : 0);
    // A cena seguinte se sobrepõe a esta durante a transição; somar a transição mantém
    // a pausa inteira depois da fala.
    const duracao = Math.ceil(segundos * FPS) + (ultima ? 0 : transicao);
    cenas.push({ id: id as CenaId, inicio: cursor, duracao, voz, vozSegundos, texto, palavras });
    cursor += duracao - transicao;
  }

  const ultimaCena = cenas[cenas.length - 1];
  const destaque = await lerJson<{ destaque: Retangulo }>('prints/resultados.json');
  return {
    durationInFrames: ultimaCena.inicio + ultimaCena.duracao,
    fps: FPS,
    props: {
      ...props,
      cenas,
      musica: arquivoSeExistir('musica.mp3') ?? arquivoSeExistir('musica-gerada.mp3'),
      destaqueResultados: destaque?.destaque ?? null,
    },
  };
};
