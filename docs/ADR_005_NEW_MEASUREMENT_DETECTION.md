# ADR 005 — Detecção de nova medição

- Status: aceita no Gate 3; hardening implementado no Pre-Gate 4
- Data: 2026-08-29

## Contexto

Chamar `get_latest_measurement` depois de solicitar uma leitura não prova novidade: sem nova operação física, o mesmo registro anterior seria devolvido. A listagem BYK também não fornece timestamp, e em bancada um ID apareceu na lista antes de seu conteúdo estar completo.

## Decisão

A aplicação cria `MeasurementSnapshot`, imutável e leve, a partir das referências existentes. Cada identidade contém serial do instrumento, ID e GUID quando disponível. ID+serial é o fallback quando algum GUID falta; GUID diferente com mesmo ID pode representar identidade nova.

`MeasurementWaitService` faz polling síncrono usando `time.monotonic`, intervalo configurável e `threading.Event` opcional. Ele nunca chama `get_latest_measurement` e nunca recupera uma identidade conhecida no snapshot.

Identidades novas são ordenadas por ID/GUID. Uma identidade deve aparecer em dois polls antes da recuperação, fornecendo uma janela inicial sem busy loop. Cada candidato entra uma única vez em `processed_candidates`, mas pode receber retries internos limitados se o retrieve ainda estiver inválido. Se todas as tentativas falham, a espera continua por outra identidade nova válida. Entre várias novas válidas, retorna a primeira por ordem de ID. Timeout, cancelamento e troca de sessão/instrumento geram erros explícitos.

Defaults operacionais: timeout de espera 60 s, intervalo de poll 0,5 s, no máximo duas falhas transitórias consecutivas de listagem, 5 retries de estabilização e intervalo de 0,5 s. O teste humano pode usar timeout maior sem alterar o default.

## Alternativas rejeitadas

- Pegar a última leitura após pedir ao operador para medir: pode reutilizar dado velho.
- Usar apenas timestamp: a listagem observada não o fornece.
- Usar apenas o maior ID sem snapshot: não prova que o registro surgiu depois do início.
- Repetir retrieve de candidato inválido em todos os polls: cria carga e loop potencialmente infinito. A alternativa adotada usa um loop interno estritamente limitado.
- Colocar polling no adaptador BYK ou no domínio: mistura política de aplicação com protocolo ou modelo puro.

## Consequências

O preflight consultou o ID 7 novamente e encontrou cinco ângulos/15 Lab completos, comprovando consistência eventual. Em seguida, o ID 10 foi publicado incompleto e ficou válido na segunda tentativa do mesmo wait. O ID 11, porém, não estabilizou nas 6 tentativas totais e ficou completo somente depois; logo a janela não pretende aguardar indefinidamente. Após esgotamento, o candidato é ignorado naquela espera e outro novo ID ainda pode ser aceito. Snapshot é estado de runtime e não é persistido.
