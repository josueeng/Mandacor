# ADR 014 — Adaptador FastAPI local

- Status: aceita e implementada no Gate P1
- Data: 2026-08-30

## Contexto

O core científico e o driver BYK foram validados antes da criação de uma interface de produto. O primeiro cliente de produto precisa de uma fronteira HTTP local sem transferir matemática, regras de pigmento, lifecycle experimental ou detalhes BYK para as rotas.

## Decisão

Adotar FastAPI como adaptador de entrada local, criado exclusivamente por `create_app()`. A factory aceita um `MandacorApiService` injetável e configuração de API, permitindo testes totalmente offline. Importar o módulo ou consultar health não inicia discovery nem conexão.

Schemas Pydantic e serializadores pertencem a `mandacor.api`. Domain e application não conhecem HTTP, status codes ou FastAPI. O serviço de API coordena os casos de uso existentes, converte exceções em erros semânticos e protege estado concorrente; ele não implementa fórmulas colorimétricas.

No MVP, haverá um instrumento conectado por processo. Sessões, operações de captura e índice de ajustes serão repositórios in-memory com locks. Capturas usam duas fases: `prepare` cria snapshot e UUID da operação; `wait` executa espera bloqueante controlada, com timeout e cancelamento cooperativo. Shutdown cancela operações e desconecta o instrumento.

O pending de ajuste aplicado e a exportação continuam nos adaptadores já implementados no Gate 10. A API não aceita caminhos de arquivo do usuário, não prevê quantidade e não altera a knowledge base.

O bind padrão é `127.0.0.1:8000`. Exposição em `0.0.0.0` é escolha explícita e gera aviso. CORS é configurável somente por origens exatas; wildcard não é aceito.

## Consequências

CLI e API permanecem adaptadores paralelos sobre o mesmo core. OpenAPI é gerado automaticamente e o futuro cliente pode depender de códigos/enums estáveis. O custo deliberado é que sessões e operações não sobrevivem ao restart; persistência de produto é decisão futura. O modelo síncrono é adequado ao driver bloqueante existente, mas uma operação `wait` ocupa a requisição até concluir, cancelar ou expirar.

Não foram introduzidos React Native, PostgreSQL, autenticação complexa, ML, Gate 11 ou recomendação quantitativa.
