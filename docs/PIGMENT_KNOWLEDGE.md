# Knowledge base inicial de pigmentos — Gate 9

Schema: `1`  
Revision: `gate-9-initial`

`UNKNOWN` significa falta de conhecimento; não significa efeito neutro. Todos os efeitos conhecidos abaixo vieram da especificação de bancada do Gate 9 e estão classificados como `SHOP_EMPIRICAL / EMPIRICAL`. Não há manual de fabricante versionado no repositório.

| Code | Family | Known effect | Front | Mid | Flop | Risks | Finish restrictions | Evidence / confidence |
|---|---|---|---|---|---|---|---|---|
| AE650 | OTHER | abre/clareia efeito angular | UNKNOWN | LIGHTEN | LIGHTEN | effect change, flop opening | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP200 | WHITE | comportamento direcional não resolvido | UNKNOWN | UNKNOWN | UNKNOWN | milky, front dirtying | not universal | SHOP_EMPIRICAL / EMPIRICAL |
| BP203 | WHITE | clareia cor lisa | LIGHTEN | LIGHTEN | LIGHTEN | — | HARD: metallic, pearl | SHOP_EMPIRICAL / EMPIRICAL |
| BP204 | COLOR | azul violetado/avermelhado | REDDER+BLUER | REDDER+BLUER | REDDER+BLUER | dirtying, hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP205 | COLOR | azul com mudança angular | GREENER+BLUER | UNKNOWN | REDDER | hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP206 | COLOR | azul escuro, flop avermelhado | DARKEN+BLUER | DARKEN+BLUER | DARKEN+REDDER+BLUER | darkening, hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP207 | COLOR | verde com tendência azul | GREENER+BLUER | GREENER+BLUER | GREENER+BLUER | hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP218 | BLACK | escurece | DARKEN | DARKEN | DARKEN | darkening, dirtying, front dirtying | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP219 | WHITE | clareia/leiteia; croma regional não resolvido | LIGHTEN | LIGHTEN | LIGHTEN | milky, hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP221 | COLOR | azul escuro avioletado/avermelhado | DARKEN+REDDER+BLUER | same | same | darkening, hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP225 | COLOR | violeta azulado | REDDER+BLUER | REDDER+BLUER | REDDER+BLUER | hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP226 | COLOR | azul limpo esverdeado | GREENER+BLUER | GREENER+BLUER | GREENER+BLUER | hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP231 | COLOR | vermelho rubi azulado | REDDER+BLUER | REDDER+BLUER | LIGHTEN+REDDER+BLUER | lightening, hue coupling | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP235 | COLOR | vermelho forte, transparente | REDDER | REDDER | REDDER | — | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP248 | BLACK | preto intenso | DARKEN | DARKEN | DARKEN | strong darkening | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP261 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP262 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP263 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP264 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP265 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP266 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP267 | ALUMINUM | UNKNOWN — menção condicional não confirmada | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP268 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP269 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP270 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP271 | ALUMINUM | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | particle/effect change | UNKNOWN | UNKNOWN / UNKNOWN |
| BP282 | PEARL | pérola azul fina | LIGHTEN+BLUER | LIGHTEN+BLUER | LIGHTEN+BLUER | particle/effect/hue | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP284 | PEARL | pérola azul graúda, mais clara de frente | LIGHTEN+BLUER | LIGHTEN+BLUER | LIGHTEN+BLUER | particle/effect/hue | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP285 | PEARL | prata brilhante, clareia | LIGHTEN | LIGHTEN | LIGHTEN | particle/effect/lightening | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP290 | PEARL | violeta azulada, clareia | LIGHTEN+BLUER | LIGHTEN+BLUER | LIGHTEN+BLUER | particle/effect/hue | none documented | SHOP_EMPIRICAL / EMPIRICAL |
| BP299 | ADDITIVE | aditivo base poliéster | UNKNOWN | UNKNOWN | UNKNOWN | — | ineligible as direct color candidate | SHOP_EMPIRICAL / EMPIRICAL |

## Limites

- Nenhum efeito é quantitativo ou por grama.
- Perfil específico prevalece sobre círculo cromático genérico.
- Não há fallback por nome, família ou sequência numérica.
- Contexto desconhecido não assume acabamento liso.

## Regras cromáticas gerais registradas

- black → DARKEN;
- white → LIGHTEN somente quando o contexto/perfil permitir;
- blue/violet → MOVE_BLUER;
- yellow → MOVE_YELLOWER;
- red/orange → MOVE_REDDER;
- green → MOVE_GREENER.

Essas regras são informativas. O avaliador Gate 9 usa exclusivamente os efeitos do perfil específico e nunca as aplica como fallback.
