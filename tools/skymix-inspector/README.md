# Exportador do SkyMix

Utilitário de leitura para o banco Access criptografado do SkyMix. Ele abre o arquivo
somente para leitura e nunca altera a origem.

Requisitos: JDK 11+ e Maven 3.9+.

```bash
cd tools/skymix-inspector
mvn -q compile dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
export SKYMIX_DB_PASSWORD='<senha do banco>'

for table in CADPROD CADFORM CADBASE CADMONT INFSGRUPO; do
  java -cp "target/classes:$(cat target/classpath.txt)" \
    br.com.jftintas.SkymixInspector \
    ../../skymix/Database/SkylacDb.accdb "$table" \
    > "/tmp/skymix-$table.csv"
done

cd ../..
python3 tools/build_formula_catalog.py /tmp data/formulas.sqlite3
```

Sem o segundo argumento, o utilitário lista tabelas, colunas e contagens para
auditoria. A senha é recebida apenas pela variável de ambiente e não é gravada no
repositório.
