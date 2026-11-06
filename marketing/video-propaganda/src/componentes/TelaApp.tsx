import React from 'react';
import { AbsoluteFill, Img } from 'remotion';

import { arquivoSeExistir } from '../arquivos';
import { config, cores } from '../config';
import { fonteNumeros, fonteTexto, fonteTitulo } from '../fontes';
import { Retangulo } from '../tipos';
import { comTransparencia } from '../util';
import { ESCALA_TELA } from './Celular';

export type TipoTela = 'resultados' | 'ficou_pior' | 'melhorou';

/** Onde fica a linha destacada nas telas recriadas (pixels da tela de 412 px). */
const DESTAQUE_RECRIADO: Retangulo = { x: 20, y: 372, w: 372, h: 34 };

type Props = {
  tipo: TipoTela;
  /** Linha destacada no print real; se faltar, usa a posição da tela recriada. */
  destaque?: Retangulo | null;
  progressoDestaque?: number;
};

/** Tela do app: usa public/prints/<tipo>.png quando existe; senão recria a tela. */
export const TelaApp: React.FC<Props> = ({ tipo, destaque = null, progressoDestaque = 0 }) => {
  const print = config.usarPrints ? arquivoSeExistir(`prints/${tipo}.png`) : null;
  const retangulo = print ? destaque : DESTAQUE_RECRIADO;
  return (
    <AbsoluteFill>
      {print ? (
        <Img src={print} style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
      ) : (
        <div style={{ width: 412, height: 892, transform: `scale(${ESCALA_TELA})`, transformOrigin: 'top left' }}>
          {tipo === 'resultados' ? <ResultadosRecriado /> : <VereditoRecriado melhorou={tipo === 'melhorou'} />}
        </div>
      )}
      {retangulo && progressoDestaque > 0 && (
        <div
          style={{
            position: 'absolute',
            left: (retangulo.x - 8) * ESCALA_TELA,
            top: (retangulo.y - 6) * ESCALA_TELA,
            width: (retangulo.w + 16) * ESCALA_TELA,
            height: (retangulo.h + 12) * ESCALA_TELA,
            border: `3px solid ${cores.tecnico}`,
            borderRadius: 12,
            backgroundColor: comTransparencia(cores.tecnico, 0.16),
            boxShadow: `0 0 ${28 * progressoDestaque}px ${comTransparencia(cores.tecnico, 0.75)}`,
            opacity: progressoDestaque,
            transform: `scale(${0.92 + 0.08 * progressoDestaque})`,
          }}
        />
      )}
    </AbsoluteFill>
  );
};

const Linha: React.FC<{ rotulo: string; valor: string }> = ({ rotulo, valor }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 12,
      padding: '11px 0',
      borderBottom: `1px solid ${cores.borda}`,
    }}
  >
    <span style={{ fontFamily: fonteTexto, fontSize: 14, color: cores.textoSecundario }}>{rotulo}</span>
    <span style={{ fontFamily: fonteNumeros, fontSize: 14, color: cores.tecnico, textAlign: 'right' }}>{valor}</span>
  </div>
);

const Cabecalho: React.FC<{ rotulo: string; titulo: string }> = ({ rotulo, titulo }) => (
  <div style={{ padding: '40px 18px 14px' }}>
    <div style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 12, letterSpacing: 2.4, color: cores.acao }}>{rotulo}</div>
    <div style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 30, color: cores.texto, marginTop: 4 }}>{titulo}</div>
  </div>
);

const Cartao: React.FC<{ children: React.ReactNode; cor?: string }> = ({ children, cor }) => (
  <div
    style={{
      margin: '10px 18px',
      padding: '16px 18px',
      borderRadius: 16,
      backgroundColor: cores.superficie,
      border: `1px solid ${cores.borda}`,
      borderLeft: cor ? `4px solid ${cor}` : `1px solid ${cores.borda}`,
    }}
  >
    {children}
  </div>
);

const BarraAbas: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      right: 0,
      bottom: 0,
      height: 70,
      display: 'flex',
      justifyContent: 'space-around',
      alignItems: 'center',
      backgroundColor: cores.fundo,
      borderTop: `1px solid ${cores.borda}`,
      fontFamily: fonteTexto,
      fontWeight: 900,
      fontSize: 10,
      color: cores.textoSecundario,
    }}
  >
    {['INÍCIO', 'MEDIR', 'RESULTADO', 'FÓRMULAS', 'CONFIG'].map((aba) => (
      <span key={aba} style={{ color: aba === 'RESULTADO' ? cores.texto : undefined }}>
        {aba}
      </span>
    ))}
  </div>
);

const ResultadosRecriado: React.FC = () => (
  <div style={{ position: 'relative', width: 412, height: 892, backgroundColor: cores.fundo }}>
    <Cabecalho rotulo="RESULTADO COLORIMÉTRICO" titulo="Como está a amostra" />
    <Cartao cor={cores.alerta}>
      <div style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 13, letterSpacing: 1.5, color: cores.texto }}>
        ÂNGULO MAIS DIFERENTE DO ALVO
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 8 }}>
        <span style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 40, color: cores.texto }}>45°</span>
        <span style={{ fontFamily: fonteNumeros, fontSize: 24, color: cores.alerta }}>2,00</span>
      </div>
      <Linha rotulo="Maior causa da diferença" valor="Claro / escuro (L*)" />
    </Cartao>
    <Cartao cor={cores.tecnico}>
      <div style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 13, letterSpacing: 1.5, color: cores.texto, marginBottom: 4 }}>
        AMOSTRA · 45°
      </div>
      <Linha rotulo="Claro / escuro (L*)" valor="2,00 mais escura que o alvo" />
      <Linha rotulo="Vermelho / verde (a*)" valor="igual ao alvo" />
      <Linha rotulo="Amarelo / azul (b*)" valor="igual ao alvo" />
      <Linha rotulo="Diferença de cor (ΔE)" valor="2,00" />
    </Cartao>
    <BarraAbas />
  </div>
);

const VereditoRecriado: React.FC<{ melhorou: boolean }> = ({ melhorou }) => {
  const cor = melhorou ? cores.sucesso : cores.perigo;
  return (
    <div style={{ position: 'relative', width: 412, height: 892, backgroundColor: cores.fundo }}>
      <Cabecalho rotulo="WORKFLOW DE BANCADA" titulo="Ajuste registrado" />
      <Cartao cor={cor}>
        <div style={{ fontFamily: fonteTexto, fontWeight: 900, fontSize: 11, letterSpacing: 1.6, color: cores.textoSecundario }}>
          ANÁLISE DO INSTRUMENTO
        </div>
        <div style={{ fontFamily: fonteTitulo, fontSize: 30, color: cor, margin: '8px 0' }}>{melhorou ? 'MELHOROU' : 'FICOU PIOR'}</div>
        <div style={{ fontFamily: fonteTexto, fontSize: 16, lineHeight: 1.4, color: cores.texto }}>
          {melhorou
            ? 'A amostra ficou mais próxima do alvo, sem piora relevante em nenhum ângulo.'
            : 'passou do ponto. A dose foi maior que o necessário.'}
        </div>
        <Linha rotulo="Diferença de cor no pior ângulo (ΔE)" valor={melhorou ? '1,20 → 0,25' : '1,20 → 2,00'} />
      </Cartao>
    </div>
  );
};
