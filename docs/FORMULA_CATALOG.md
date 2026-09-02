# Catálogo de fórmulas SkyMix

## Fonte e escopo

O catálogo do MANDACOR foi gerado do banco vigente
`skymix/Database/SkylacDb.accdb`. A importação preserva as versões, condições,
embalagens, ordem dos componentes e massas em gramas registradas no SkyMix.

Contagens auditadas em 1 de setembro de 2026:

- 12.198 cores acessíveis (12.195 cadastros de cor e 3 fórmulas órfãs preservadas);
- 14.069 variações de fórmula;
- 97.677 componentes/quantidades ativos;
- 109.541 linhas de componentes na origem, incluindo revisões substituídas;
- 7.984 cores poliéster, 2.162 PU, 819 laca, 1.204 esmalte sintético e 29 epóxi.

Os backups históricos foram comparados com a fonte vigente. Eles contêm fórmulas
substituídas e não foram mesclados, evitando apresentar uma composição obsoleta como
atual. Versões históricas que continuam registradas no banco vigente foram mantidas.

## API

- `GET /api/v1/formulas?q=vermelho&system=POLIESTER&limit=30&offset=0`
- `GET /api/v1/formulas/{codigo}`
- `GET /api/v1/formulas/catalog`
- `POST /api/v1/formulas`
- `PUT /api/v1/formulas/{codigo}`
- `DELETE /api/v1/formulas/{codigo}`
- `GET|POST /api/v1/formulas/{codigo}/readings`
- `GET /api/v1/formulas/spectral-matches?session_id=...&measurement_role=sample`

Sistemas aceitos: `POLIESTER`, `PU`, `LACA`, `ESMALTE_SINTETICO` e `EPOXI`.
A busca ignora acentos e aceita múltiplos termos em qualquer ordem.

## Atualização

O processo reproduzível está descrito em `tools/skymix-inspector/README.md`. O
arquivo `data/formulas.sqlite3` contém o catálogo importado e a camada editável do
MANDACOR. Inclusões e alterações são identificadas por origem e data; exclusões são
lógicas para preservar rastreabilidade e leituras associadas.

## Dataset de leituras

Cada registro em `paint_readings` preserva a tinta e uma cópia completa da fórmula
no momento da captura, a sessão, o ID/GUID da medição, o aparelho e L*, a* e b* nos
ângulos 15°, 25°, 45°, 75° e 105°. Assim, editar a tinta depois não modifica o dado
histórico usado em um ajuste futuro.

A interface exige indicar qual variante/condição de fórmula foi realmente preparada.
O `formula_id` selecionado e o snapshot com componentes e massas são preservados;
sem essa escolha, os dados seriam ambíguos para modelagem de pigmentos.

Nas tintas metálicas, a leitura exige uma das granulometrias `FINO`, `MEDIO_FINO`,
`MEDIO`, `GROSSEIRO` ou `MUITO_GROSSEIRO`.

Novas coletas usam o schema `2`, fingerprint SHA-256 da identidade e dos 15 valores
Lab, estado de qualidade e contexto de captura. Uma mesma medição física não pode ser
salva novamente, nem mesmo sob outra cor. Registros legados recebem fingerprint na
migração e permanecem como `legacy_unverified`, sem ganhar qualidade fictícia.

O dataset versionado para experimentos futuros pode ser exportado em JSONL:

```bash
python -m mandacor dataset export-formula-training
```

Por padrão, somente registros `eligible` são exportados. `--include-review` inclui
registros que precisam de revisão. Cada exemplo preserva `group_key=product_code`,
snapshot completo da fórmula, espectro multiângulo, proveniência e flags de qualidade.
O manifesto contém hash SHA-256 e determina que divisões de treino/validação sejam
feitas por cor, nunca separando leituras da mesma cor entre os conjuntos.

A porcentagem da busca espectral é um índice de ordenação derivado do ΔE76 RMS dos
cinco ângulos; não é probabilidade calibrada de acerto nem substitui validação visual.
