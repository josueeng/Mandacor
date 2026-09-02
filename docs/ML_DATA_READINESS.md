# Preparação de dados para aprendizado de cor

## Objetivos separados

O MANDACOR mantém dois conjuntos com semânticas diferentes:

1. `paint_readings` / `formula_spectra.jsonl`: espectro multiângulo de uma tinta e
   snapshot da fórmula que a produziu. Serve para recuperação de cores e, com dados
   suficientes, modelagem composição ↔ cor.
2. `adjustments.csv` + `adjustment_components.csv`: TARGET, BEFORE, pigmentos e massas
   realmente adicionadas, volume e AFTER. Este é o conjunto causal para aprender a
   resposta de cada pigmento e quantidade.

Misturar os dois como se fossem o mesmo alvo cria rótulos falsos. Uma fórmula final
não informa isoladamente qual componente causou uma mudança observada.

## Garantias implementadas

- cinco ângulos obrigatórios e exatamente 15 valores CIELAB finitos;
- L* validado entre 0 e 100 antes de entrar no dataset de fórmulas;
- captura aceita somente medição posterior ao snapshot;
- fingerprint SHA-256 e rejeição de medição física duplicada;
- snapshots imutáveis de fórmula, componentes, posições e massas;
- schema versionado, proveniência, timestamps, GUID e serial do instrumento;
- qualidade `eligible`, `review` ou `legacy_unverified`, sem preencher dados ausentes;
- exportação JSONL atômica com manifesto e hash;
- trials multicomponente marcados e nunca atribuídos artificialmente a um pigmento;
- quantidades e volumes são somente os informados pelo operador.

## Protocolo de coleta recomendado

- calibrar e registrar o instrumento conforme o procedimento do fabricante;
- manter substrato, fundo, pistola, pressão, diluição, número de demãos, flash-off,
  cura, verniz e temperatura controlados;
- fazer réplicas independentes por tinta/lote e registrar observações de aplicação;
- nos estudos de efeito, preferir um pigmento por trial e variar doses controladas;
- nunca reutilizar a leitura BEFORE como AFTER;
- registrar feedback visual depois da leitura, sem alterar os valores instrumentais;
- preservar falhas e rejeições como flags, não apagá-las silenciosamente.

## Divisão e avaliação futuras

- dividir treino/validação/teste por `product_code`, lote e campanha temporal;
- impedir que réplicas da mesma chapinha apareçam em conjuntos diferentes;
- reservar instrumentos/lotes não vistos para medir generalização;
- avaliar ΔE por ângulo, erro do vetor AFTER−BEFORE e segurança da dosagem;
- calibrar qualquer “porcentagem de compatibilidade” antes de tratá-la como
  probabilidade;
- manter regras determinísticas e revisão humana como proteção do modelo.

## Critério para iniciar treinamento

Não há quantidade mínima universal. Antes do primeiro modelo operacional, auditar
cobertura por pigmento, sistema, acabamento, dose, volume e faixa de cor; número de
réplicas; taxa de `eligible`; drift por instrumento; e representatividade dos casos
metálicos/perolizados. Até essa auditoria, o sistema deve continuar apresentando
ranking e evidência colorimétrica, sem calcular automaticamente gramas de pigmento.
