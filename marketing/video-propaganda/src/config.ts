import narracao from '../narracao.json';

/**
 * O que costuma mudar no vídeo fica neste arquivo.
 * A fala de cada cena fica em narracao.json (depois de mudar, rode scripts/gerar_voz.py).
 */
export const config = {
  /** Número exibido no cartão final. */
  whatsapp: '[WHATSAPP]',
  /** false: recria as telas do app em vez de usar os prints de public/prints. */
  usarPrints: true,
  /** Pausa depois de cada fala, antes da próxima cena. */
  respiroSegundos: 0.6,
  /** Tempo extra no fim, para a chamada final ficar na tela. */
  seguraFinalSegundos: 1,
  transicaoFrames: 10,
  volumes: {
    voz: 1,
    musica: 0.25,
    musicaDuranteFala: 0.08,
    efeitos: 0.5,
  },
  textos: {
    1: { titulo: 'Acertar cor no olho?', destaque: 'no olho?' },
    2: { titulo: 'No metálico, cada ângulo é uma cor.', destaque: 'cada ângulo' },
    3: {
      titulo: 'Lê os 5 ângulos e explica na língua da bancada.',
      destaque: '5 ângulos',
      frase: '2,00 mais escura que o alvo',
    },
    4: {
      titulo: 'Avisa quando piorou ou passou do ponto.',
      destaque: 'passou do ponto',
      alerta: 'FICOU PIOR',
      detalhe: 'passou do ponto',
    },
    5: {
      titulo: 'Guarda cada ajuste no histórico.',
      destaque: 'histórico',
      resultado: 'MELHOROU',
      detalhe: 'mais próxima do alvo',
    },
    6: {
      marca: 'MANDACOR',
      subtitulo: 'A cor certa com menos tentativa.',
      cartao: 'Demonstração grátis na sua loja',
    },
  },
  narracao,
} as const;

/** Cores do aplicativo MANDACOR. */
export const cores = {
  fundo: '#090C10',
  superficie: '#12171D',
  superficieAlta: '#1A2129',
  borda: '#28323D',
  texto: '#F4F7FA',
  textoSecundario: '#9DAAB8',
  tecnico: '#49AEF8',
  acao: '#E4474D',
  sucesso: '#44C983',
  alerta: '#F0B94F',
  perigo: '#FF666B',
} as const;

export const VERSOES = {
  completa: { cenas: [1, 2, 3, 4, 5, 6], prefixoVoz: 'voz/cena-' },
  curta: { cenas: [1, 3, 4, 5, 6], prefixoVoz: 'voz/curta-cena-' },
} as const;
