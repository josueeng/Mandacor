package br.com.jftintas;

import io.github.spannm.jackcess.Column;
import io.github.spannm.jackcess.Database;
import io.github.spannm.jackcess.DatabaseBuilder;
import io.github.spannm.jackcess.Row;
import io.github.spannm.jackcess.Table;
import io.github.spannm.jackcess.encrypt.CryptCodecProvider;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class SkymixInspector {
    private SkymixInspector() {}

    public static void main(String[] args) throws Exception {
        if (args.length < 1 || args.length > 2) {
            throw new IllegalArgumentException("usage: SkymixInspector <database.accdb> [table]");
        }
        String password = System.getenv("SKYMIX_DB_PASSWORD");
        if (password == null || password.isBlank()) {
            throw new IllegalArgumentException("SKYMIX_DB_PASSWORD is required");
        }
        try (Database database = new DatabaseBuilder()
                .withFile(new File(args[0]))
                .withReadOnly(true)
                .withCodecProvider(new CryptCodecProvider(password))
                .open()) {
            if (args.length == 2) {
                exportTable(database.getTable(args[1]));
                return;
            }
            List<String> names = new ArrayList<>(database.getTableNames());
            Collections.sort(names);
            for (String name : names) {
                Table table = database.getTable(name);
                long rows = 0;
                for (Row ignored : table) {
                    rows++;
                }
                StringBuilder columns = new StringBuilder();
                for (Column column : table.getColumns()) {
                    if (columns.length() > 0) columns.append(", ");
                    columns.append(column.getName()).append(":").append(column.getType());
                }
                System.out.printf("%s\t%d\t%s%n", name, rows, columns);
            }
        }
    }

    private static void exportTable(Table table) throws Exception {
        List<? extends Column> columns = table.getColumns();
        System.out.println(columns.stream().map(Column::getName).map(SkymixInspector::csv).reduce((a, b) -> a + "," + b).orElse(""));
        for (Row row : table) {
            StringBuilder line = new StringBuilder();
            for (Column column : columns) {
                if (line.length() > 0) line.append(',');
                Object value = row.get(column.getName());
                line.append(csv(value == null ? "" : value.toString()));
            }
            System.out.println(line);
        }
    }

    private static String csv(String value) {
        return "\"" + value.replace("\"", "\"\"").replace("\r\n", "\n").replace("\r", "\n") + "\"";
    }
}
