# Fixtures BYK do Gate 0

Classificação atual: **REAL_CAPTURE** para os arquivos enumerados em
`CAPTURE_METADATA.json`.

Nenhuma resposta do instrumento ou medição real existia no repositório ao
iniciar o Gate 0. Após o equipamento ser ligado, uma sessão somente leitura
capturou discovery, requests, respostas, XMLs, CRC e uma medição armazenada.
Os hashes, origem e identidade estão no arquivo de metadados. Os dados literais
adicionais dos testes continuam marcados `SYNTHETIC_TEST_DATA`.

Estrutura reservada:

- `discovery/`: `BYKQUERY.bin`, `BYKINSTRUMENT.bin` e metadados da captura;
- `tcp/`: streams de requisição/resposta sem modificação;
- `frames/`: header, payload e CRC separados, acompanhados de hashes;
- `xml/`: XML UTF-8 extraído de resposta real;
- `measurements/`: valores esperados derivados da mesma medição real.

Toda captura deverá registrar origem, data, firmware, operação read-only,
hash SHA-256 e eventual sanitização. Alterar bytes de framing/CRC faz a fixture
deixar de ser captura original.
