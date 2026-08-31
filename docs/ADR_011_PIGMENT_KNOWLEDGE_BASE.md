# ADR 011 — Knowledge base e seleção qualitativa de pigmentos

- Status: aceita e implementada no Gate 9
- Data: 2026-08-30

## Contexto

`ColorCorrectionNeed` descreve o destino Lab, mas não qual ação física pode produzi-lo. Efeitos de pigmento são contextuais, frequentemente acoplados e podem variar entre front, mid e flop. Ausência de conhecimento não pode virar neutralidade nem ser preenchida pelo nome ou pela proximidade do código.

## Decisão

A knowledge base usa perfis Python fortemente tipados e imutáveis, com `knowledge_schema_version=1` e revisão explícita. Cada perfil contém código estável, família, compatibilidades, efeitos por região, partícula, riscos, contraindicações, notas, provenance e confiança.

Os fatos descritos no documento do Gate 9 são `SHOP_EMPIRICAL/EMPIRICAL`, pois não há manual de fabricante no repositório. BP261–BP271 são registrados como alumínios, mas efeitos e partículas permanecem `UNKNOWN`; nem BP267 recebe o efeito mencionado condicionalmente sem confirmação independente.

`evaluate_pigment_candidates` percorre cada ângulo e eixo, comparando necessidade e efeito específico. UNKNOWN não conta como match nem neutral. Efeito oposto vira conflito. Hard contraindications removem o perfil da lista de candidatos; soft risks permanecem visíveis.

## Ranking determinístico

Após contraindicações, a ordem é:

1. zero conflito no primary issue;
2. match no primary issue;
3. mais matches ângulo-eixo;
4. menos conflitos secundários;
5. menos efeitos desconhecidos;
6. código em ordem lexical como desempate.

Não há pesos, score, aleatoriedade ou escolha por ΔE hipotético.

## Consequências

Uma saída pode declarar `NO_SINGLE_SAFE_CANDIDATE`. Candidato significa compatibilidade qualitativa sob regras atuais, nunca certeza. Dose, volume e alteração de fórmula não existem. Toda ação física requer teste em chapinha e medição posterior.
