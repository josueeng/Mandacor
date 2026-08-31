# ADR 004 — Modelo de domínio Measurement

- Status: aceita e implementada no Gate 2
- Data: 2026-08-29

## Contexto

O XML BYK pode omitir coordenadas ou conter valores inválidos, enquanto o restante do MANDACOR precisa receber sempre uma leitura confiável, independente de fabricante e transporte.

## Decisão

Adotar duas representações:

1. DTOs `RawByk*`, congelados, refletem strings e ausências do protocolo.
2. `Measurement` de domínio só é construída pelo mapper após validação completa.

O domínio usa dataclasses `frozen=True, slots=True`:

- `MeasurementAngle(IntEnum)`: 15, 25, 45, 75, 105;
- `LabValue(L, a, b)`: floats finitos;
- `MeasurementReference`: ID/GUID/nome/timestamp quando disponível;
- `Measurement`: identidade, metadados e mapping imutável de ângulos.

O mapping é copiado e protegido por `MappingProxyType`. Exige exatamente os cinco ângulos; nenhuma coordenada pode ser `None`, string, NaN ou infinito. Nenhum valor é arredondado ou preenchido com zero.

## Timestamp e identidade

O mapper usa `datetime.fromisoformat`. Um offset presente é preservado; timestamp sem offset permanece naive, sem inventar UTC. `timestamp_raw` conserva o texto original. ID, GUID, nome e serial do instrumento são preservados quando presentes. IP, porta, socket e heartbeat nunca entram em `Measurement`.

## Listagem e latest

A fixture real de listagem não contém timestamp; apenas ID/nome/GUID. Portanto:

- a lista pública é ordenada por ID ascendente para determinismo e preserva duplicatas;
- `get_latest_reference` escolhe maior ID, como política BYK baseada na evidência atual, sem declarar especificação universal;
- `get_latest_measurement` tenta IDs distintos em ordem decrescente e retorna a primeira medição validada;
- lista vazia ou nenhum candidato válido gera `MeasurementNotFoundError`.

Gate 3 deverá usar snapshot de identidades e não depender apenas desta ordenação para definir "nova" leitura.

## Consequências

Adapters futuros podem mapear seus formatos para o mesmo domínio. A separação adiciona um mapper explícito, mas impede que detalhes BYK e dados incompletos atravessem a fronteira. Serialização e comparação permanecem fora deste Gate.

