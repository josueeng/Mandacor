"""Build the read-only MANDACOR formula catalog from SkyMix CSV exports."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path


GROUPS = {
    "2": ("POLIESTER", "Poliéster", "SKYDUR"),
    "4": ("ESMALTE_SINTETICO", "Esmalte sintético", "SKYLUX"),
    "5": ("LACA", "Laca nitrocelulose", "SKYLAC"),
    "6": ("PU", "PU", "SKYDUR"),
    "E": ("EPOXI", "Epóxi", "SKYFROTA"),
    "L": ("LACA", "Laca", "SKYFROTA"),
    "P": ("PU", "PU", "SKYFROTA"),
    "S": ("ESMALTE_SINTETICO", "Esmalte sintético", "SKYFROTA"),
}


def normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def read_csv(directory: Path, table: str) -> list[dict[str, str]]:
    with (directory / f"skymix-{table}.csv").open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def infer_group(product_code: str) -> str:
    return product_code[:1] if product_code[:1] in {"2", "4", "5", "6"} else "6"


def build(source_dir: Path, output: Path) -> None:
    products = read_csv(source_dir, "CADPROD")
    formula_rows = read_csv(source_dir, "CADFORM")
    bases = {row["CODBASE"]: row for row in read_csv(source_dir, "CADBASE")}
    makers = {row["COD_MONT"]: row["MONTADORA"] for row in read_csv(source_dir, "CADMONT")}
    finishes = {row["SGRUPO"]: row["ASPECTO"] for row in read_csv(source_dir, "INFSGRUPO")}

    products_by_code = {row["CODPROD"]: row for row in products}
    for code in sorted({row["CODPROD"] for row in formula_rows} - products_by_code.keys()):
        products.append({
            "CODPROD": code, "DESC_PTB": "Fórmula sem cadastro de cor no SkyMix",
            "ANO": "", "CODUNIV": "", "ANUANCIA": "", "COR_PAI": "",
            "NAC_IMP": "", "CD_MONT": "", "OBSCON": "", "OBSPROD": "",
            "GRUPO": infer_group(code), "SGRUPO": "", "IR_BASE": "",
            "DESC_ING": "", "DESC_ESP": "", "PERSONALIZADO": "false",
        })

    revisions: dict[tuple[str, str, str, int], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in formula_rows:
        key = (row["CODPROD"], row["CONDIL"], row["QUANT"], int(row["VERSAO"]))
        revisions[key][row["DATA_ATU"]].append(row)

    # SkyMix may keep several dated revisions under the same version number.
    # Only the most recent date represents the formula shown by SkyMix; merging
    # those rows would concatenate obsolete and current compositions.
    variants = {
        key: dated_rows[max(dated_rows)]
        for key, dated_rows in revisions.items()
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    connection = sqlite3.connect(output)
    connection.executescript("""
        PRAGMA journal_mode = DELETE;
        PRAGMA foreign_keys = ON;
        CREATE TABLE products (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            year TEXT NOT NULL,
            universal_code TEXT NOT NULL,
            nuance TEXT NOT NULL,
            manufacturer_code TEXT NOT NULL,
            manufacturer TEXT NOT NULL,
            observations TEXT NOT NULL,
            group_code TEXT NOT NULL,
            system TEXT NOT NULL,
            system_label TEXT NOT NULL,
            paint_line TEXT NOT NULL,
            finish_code TEXT NOT NULL,
            finish_label TEXT NOT NULL,
            personalized INTEGER NOT NULL,
            search_text TEXT NOT NULL
        );
        CREATE TABLE formula_variants (
            id INTEGER PRIMARY KEY,
            product_code TEXT NOT NULL REFERENCES products(code),
            condition TEXT NOT NULL,
            package TEXT NOT NULL,
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            total_weight_g REAL NOT NULL,
            UNIQUE(product_code, condition, package, version)
        );
        CREATE TABLE formula_components (
            formula_id INTEGER NOT NULL REFERENCES formula_variants(id),
            position INTEGER NOT NULL,
            base_code TEXT NOT NULL,
            base_name TEXT NOT NULL,
            weight_g REAL NOT NULL,
            PRIMARY KEY(formula_id, position)
        );
        CREATE INDEX idx_products_system ON products(system);
        CREATE INDEX idx_products_search ON products(search_text);
        CREATE INDEX idx_variants_product ON formula_variants(product_code);
        CREATE INDEX idx_components_formula ON formula_components(formula_id);
    """)

    for row in products:
        group = GROUPS[row["GRUPO"]]
        manufacturer = makers.get(row["CD_MONT"], "")
        searchable = normalized(" ".join((
            row["CODPROD"], row["DESC_PTB"], row["ANO"], row["CODUNIV"],
            row["ANUANCIA"], manufacturer,
        )))
        connection.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row["CODPROD"], row["DESC_PTB"], row["ANO"], row["CODUNIV"],
                row["ANUANCIA"], row["CD_MONT"], manufacturer,
                row["OBSPROD"] or row["OBSCON"], row["GRUPO"], group[0], group[1],
                group[2], row["SGRUPO"], finishes.get(row["SGRUPO"], ""),
                int(row["PERSONALIZADO"].lower() == "true"),
                searchable,
            ),
        )

    for key in sorted(variants):
        rows = variants[key]
        updated_at = rows[0]["DATA_ATU"]
        total = sum(float(row["PESO_GR"]) for row in rows)
        cursor = connection.execute(
            "INSERT INTO formula_variants(product_code, condition, package, version, updated_at, total_weight_g) VALUES (?, ?, ?, ?, ?, ?)",
            (*key, updated_at, total),
        )
        formula_id = cursor.lastrowid
        for position, row in enumerate(rows, start=1):
            base = bases.get(row["BASE"], {})
            connection.execute(
                "INSERT INTO formula_components VALUES (?, ?, ?, ?, ?)",
                (formula_id, position, row["BASE"], base.get("MIXING", ""), float(row["PESO_GR"])),
            )

    connection.execute("CREATE TABLE catalog_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    metadata = {
        "source": "skymix/Database/SkylacDb.accdb",
        "products": str(len(products)),
        "formulas": str(len(variants)),
        "components": str(sum(len(rows) for rows in variants.values())),
        "source_components": str(len(formula_rows)),
    }
    connection.executemany("INSERT INTO catalog_metadata VALUES (?, ?)", metadata.items())
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path, help="directory containing skymix-*.csv exports")
    parser.add_argument("output", type=Path, help="SQLite catalog to create")
    args = parser.parse_args()
    build(args.source_dir, args.output)


if __name__ == "__main__":
    main()
