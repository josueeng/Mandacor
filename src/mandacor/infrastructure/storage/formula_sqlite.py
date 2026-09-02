from __future__ import annotations

import json
import hashlib
import math
import sqlite3
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mandacor.domain.formulas import (
    FormulaComponent,
    FormulaProduct,
    FormulaSearchResult,
    FormulaVariant,
)


FORMULA_SYSTEMS = frozenset({"POLIESTER", "PU", "LACA", "ESMALTE_SINTETICO", "EPOXI"})
DISPLAY_CODE_PREFIXES = {
    "POLIESTER": "210",
    "PU": "610",
    "LACA": "510",
    "ESMALTE_SINTETICO": "410",
}
PAINT_READING_SCHEMA_VERSION = 2


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def _measurement_fingerprint(
    *, instrument_serial: str, measurement_guid: str | None,
    measurement_id: int, angles: list[dict]
) -> str:
    payload = {
        "instrument_serial": instrument_serial,
        "measurement_guid": measurement_guid,
        "measurement_id": measurement_id,
        "angles": angles,
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def formula_display_code(product_code: str, system: str) -> str:
    """Return the commercial SkyMix code without exposing variant suffixes."""
    prefix = DISPLAY_CODE_PREFIXES.get(system)
    if prefix and len(product_code) == 12:
        return f"{prefix}-{product_code[3:8]}"
    return product_code


def _commercial_code_parts(query: str) -> tuple[str, str] | None:
    compact = "".join(char for char in query.strip() if char.isalnum())
    if len(compact) != 8 or not compact.isdigit():
        return None
    prefix = compact[:3]
    system = next(
        (name for name, expected_prefix in DISPLAY_CODE_PREFIXES.items() if expected_prefix == prefix),
        None,
    )
    return (system, compact[3:]) if system else None


class FormulaCatalogNotFoundError(LookupError):
    pass


class DuplicateFormulaReadingError(ValueError):
    def __init__(self, product_code: str, measurement_id: int) -> None:
        self.product_code = product_code
        self.measurement_id = measurement_id
        super().__init__(
            f"measurement {measurement_id} is already saved in dataset color {product_code}"
        )


class SqliteFormulaCatalog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._initialize_editable_schema()

    def _connect(self, *, writable: bool = False) -> sqlite3.Connection:
        connection = (
            sqlite3.connect(self.path.resolve())
            if writable
            else sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True)
        )
        connection.row_factory = sqlite3.Row
        connection.create_function("mandacor_normalize", 1, _normalized, deterministic=True)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_editable_schema(self) -> None:
        with self._connect(writable=True) as connection:
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(products)")
            }
            if "origin" not in columns:
                connection.execute(
                    "ALTER TABLE products ADD COLUMN origin TEXT NOT NULL DEFAULT 'SKYMIX'"
                )
            if "modified_at" not in columns:
                connection.execute("ALTER TABLE products ADD COLUMN modified_at TEXT")
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE products ADD COLUMN deleted_at TEXT")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS paint_readings (
                    reading_id TEXT PRIMARY KEY,
                    product_code TEXT NOT NULL REFERENCES products(code),
                    session_id TEXT NOT NULL,
                    measurement_role TEXT NOT NULL,
                    metallic_grain TEXT,
                    notes TEXT NOT NULL,
                    measurement_id INTEGER NOT NULL,
                    measurement_guid TEXT,
                    measurement_timestamp TEXT,
                    measurement_name TEXT,
                    instrument_serial TEXT NOT NULL,
                    angles_json TEXT NOT NULL,
                    formula_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_paint_readings_product
                    ON paint_readings(product_code, created_at);
            """)
            reading_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(paint_readings)")
            }
            if "formula_json" not in reading_columns:
                connection.execute(
                    "ALTER TABLE paint_readings ADD COLUMN formula_json TEXT NOT NULL DEFAULT '{}'"
                )
            for column, definition in (
                ("schema_version", "INTEGER NOT NULL DEFAULT 1"),
                ("measurement_fingerprint", "TEXT"),
                ("quality_status", "TEXT NOT NULL DEFAULT 'legacy_unverified'"),
                ("quality_issues_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("capture_context_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("formula_id", "INTEGER"),
            ):
                if column not in reading_columns:
                    connection.execute(
                        f"ALTER TABLE paint_readings ADD COLUMN {column} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_paint_readings_fingerprint "
                "ON paint_readings(measurement_fingerprint)"
            )
            legacy_rows = connection.execute(
                "SELECT reading_id,instrument_serial,measurement_guid,measurement_id,angles_json "
                "FROM paint_readings WHERE measurement_fingerprint IS NULL"
            ).fetchall()
            for row in legacy_rows:
                try:
                    angles = json.loads(row["angles_json"])
                    fingerprint = _measurement_fingerprint(
                        instrument_serial=row["instrument_serial"],
                        measurement_guid=row["measurement_guid"],
                        measurement_id=row["measurement_id"],
                        angles=angles,
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                connection.execute(
                    "UPDATE paint_readings SET measurement_fingerprint=? WHERE reading_id=?",
                    (fingerprint, row["reading_id"]),
                )

    def metadata(self) -> dict[str, str]:
        with self._connect() as connection:
            return dict(connection.execute("SELECT key, value FROM catalog_metadata"))

    def search(
        self,
        query: str = "",
        system: str | None = None,
        *,
        manufacturer: str = "",
        year: str = "",
        finish: str = "",
        universal_code: str = "",
        limit: int = 30,
        offset: int = 0,
    ) -> FormulaSearchResult:
        if system is not None:
            system = system.strip().upper()
            if system not in FORMULA_SYSTEMS:
                raise ValueError(f"unsupported formula system: {system}")
        commercial_code = _commercial_code_parts(query)
        terms = [] if commercial_code else [term for term in _normalized(query.strip()).split() if term]
        clauses: list[str] = []
        parameters: list[object] = []
        clauses.append("p.deleted_at IS NULL")
        if system:
            clauses.append("p.system = ?")
            parameters.append(system)
        if commercial_code:
            code_system, color_number = commercial_code
            commercial_text = f"{DISPLAY_CODE_PREFIXES[code_system]}-{color_number}"
            clauses.extend(("p.system = ?", "(substr(p.code, 4, 5) = ? OR p.code = ?)"))
            parameters.extend((code_system, color_number, commercial_text))
        for term in terms:
            clauses.append("p.search_text LIKE ?")
            parameters.append(f"%{term}%")
        for column, value in (
            ("manufacturer", manufacturer),
            ("year", year),
            ("finish_label", finish),
            ("universal_code", universal_code),
        ):
            normalized_filter = _normalized(value.strip())
            if normalized_filter:
                clauses.append(f"mandacor_normalize(p.{column}) LIKE ?")
                parameters.append(f"%{normalized_filter}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM products p {where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT p.*, COUNT(v.id) AS formula_count,
                       (SELECT COUNT(*) FROM paint_readings r WHERE r.product_code = p.code) AS reading_count
                FROM products p
                JOIN formula_variants v ON v.product_code = p.code
                {where}
                GROUP BY p.code
                ORDER BY p.description COLLATE NOCASE, p.code
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()
        return FormulaSearchResult(
            tuple(self._product(row) for row in rows), total, limit, offset
        )

    def get(self, product_code: str) -> FormulaProduct:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT p.*, COUNT(v.id) AS formula_count,
                       (SELECT COUNT(*) FROM paint_readings r WHERE r.product_code = p.code) AS reading_count
                FROM products p JOIN formula_variants v ON v.product_code = p.code
                WHERE p.code = ? AND p.deleted_at IS NULL GROUP BY p.code
                """,
                (product_code.strip(),),
            ).fetchone()
            if row is None:
                raise FormulaCatalogNotFoundError(product_code)
            variants = []
            for variant_row in connection.execute(
                "SELECT * FROM formula_variants WHERE product_code = ? ORDER BY version DESC, condition, package",
                (row["code"],),
            ):
                components = tuple(
                    FormulaComponent(
                        position=item["position"],
                        base_code=item["base_code"],
                        base_name=item["base_name"],
                        weight_g=item["weight_g"],
                    )
                    for item in connection.execute(
                        "SELECT * FROM formula_components WHERE formula_id = ? ORDER BY position",
                        (variant_row["id"],),
                    )
                )
                variants.append(
                    FormulaVariant(
                        formula_id=variant_row["id"],
                        condition=variant_row["condition"],
                        package=variant_row["package"],
                        version=variant_row["version"],
                        updated_at=variant_row["updated_at"],
                        total_weight_g=variant_row["total_weight_g"],
                        components=components,
                    )
                )
        return self._product(row, tuple(variants))

    def create(self, values: dict) -> FormulaProduct:
        code = values["code"].strip().upper()
        with self._lock, self._connect(writable=True) as connection:
            commercial = _commercial_code_parts(code)
            if commercial:
                code_system, color_number = commercial
                duplicate = connection.execute(
                    """SELECT 1 FROM products
                       WHERE deleted_at IS NULL AND system=?
                         AND (substr(code, 4, 5)=? OR code=?) LIMIT 1""",
                    (code_system, color_number, code),
                ).fetchone()
            else:
                duplicate = connection.execute(
                    "SELECT 1 FROM products WHERE code = ? AND deleted_at IS NULL", (code,)
                ).fetchone()
            if duplicate:
                raise ValueError(f"formula {code} already exists")
            self._insert_product(connection, code, values, origin="USER")
            self._replace_variants(connection, code, values["variants"])
        return self.get(code)

    def update(self, product_code: str, values: dict) -> FormulaProduct:
        with self._lock, self._connect(writable=True) as connection:
            current = connection.execute(
                "SELECT code FROM products WHERE code = ? AND deleted_at IS NULL",
                (product_code.strip(),),
            ).fetchone()
            if current is None:
                raise FormulaCatalogNotFoundError(product_code)
            code = current["code"]
            now = datetime.now(timezone.utc).isoformat()
            search_text = self._search_text(code, values)
            connection.execute(
                """
                UPDATE products SET description=?, year=?, universal_code=?, nuance=?,
                    manufacturer_code='', manufacturer=?, observations=?, group_code=?,
                    system=?, system_label=?, paint_line=?, finish_code='', finish_label=?,
                    personalized=1, search_text=?, modified_at=? WHERE code=?
                """,
                (
                    values["description"], values.get("year", ""),
                    values.get("universal_code", ""), values.get("nuance", ""),
                    values.get("manufacturer", ""), values.get("observations", ""),
                    self._group_code(values["system"]), values["system"],
                    self._system_label(values["system"]), self._paint_line(values["system"]),
                    values.get("finish_label", ""), search_text, now, code,
                ),
            )
            self._replace_variants(connection, code, values["variants"])
        return self.get(code)

    def delete(self, product_code: str) -> None:
        with self._lock, self._connect(writable=True) as connection:
            cursor = connection.execute(
                "UPDATE products SET deleted_at=?, modified_at=? WHERE code=? AND deleted_at IS NULL",
                (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), product_code.strip()),
            )
            if cursor.rowcount == 0:
                raise FormulaCatalogNotFoundError(product_code)

    def save_reading(
        self,
        product_code: str,
        *,
        session_id: str,
        role: str,
        formula_id: int | None = None,
        metallic_grain: str | None,
        notes: str,
        measurement,
    ) -> dict:
        product = self.get(product_code)
        selected_variant = next(
            (variant for variant in product.variants if variant.formula_id == formula_id),
            None,
        )
        if formula_id is not None and selected_variant is None:
            raise ValueError("formula_id does not belong to the selected color")
        if "METAL" in _normalized(product.finish_label).upper() and not metallic_grain:
            raise ValueError("metallic_grain is required for metallic paint")
        reading_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        angles = [
            {"angle": int(angle), "l": value.L, "a": value.a, "b": value.b}
            for angle, value in sorted(measurement.angles.items(), key=lambda item: int(item[0]))
        ]
        if any(not 0 <= item["l"] <= 100 for item in angles):
            raise ValueError("CIELAB L* values must be between 0 and 100")
        instrument_serial = measurement.instrument_serial or ""
        measurement_fingerprint = _measurement_fingerprint(
            instrument_serial=instrument_serial,
            measurement_guid=measurement.guid,
            measurement_id=measurement.measurement_id,
            angles=angles,
        )
        quality_issues = []
        if not instrument_serial:
            quality_issues.append("missing_instrument_serial")
        if not measurement.guid:
            quality_issues.append("missing_measurement_guid")
        if not measurement.timestamp and not measurement.timestamp_raw:
            quality_issues.append("missing_measurement_timestamp")
        if len({(item["l"], item["a"], item["b"]) for item in angles}) == 1:
            quality_issues.append("identical_values_at_all_angles")
        if selected_variant is None:
            quality_issues.append("missing_selected_formula_variant")
        quality_status = "eligible" if not quality_issues else "review"
        capture_context = {
            "color_space": "CIELAB",
            "angles_degrees": [item["angle"] for item in angles],
            "illuminant": None,
            "observer": None,
            "measurement_geometry": None,
        }
        formula_snapshot = {
            "code": product.code,
            "display_code": product.display_code,
            "description": product.description,
            "system": product.system,
            "finish_label": product.finish_label,
            "manufacturer": product.manufacturer,
            "year": product.year,
            "universal_code": product.universal_code,
            "selected_formula_id": formula_id,
            "variants": [
                {
                    "formula_id": variant.formula_id,
                    "condition": variant.condition,
                    "package": variant.package,
                    "version": variant.version,
                    "total_weight_g": variant.total_weight_g,
                    "components": [
                        {
                            "base_code": component.base_code,
                            "base_name": component.base_name,
                            "weight_g": component.weight_g,
                        }
                        for component in variant.components
                    ],
                }
                for variant in product.variants
            ],
        }
        with self._lock, self._connect(writable=True) as connection:
            duplicate = connection.execute(
                "SELECT product_code FROM paint_readings WHERE measurement_fingerprint=? LIMIT 1",
                (measurement_fingerprint,),
            ).fetchone()
            if duplicate is not None:
                raise DuplicateFormulaReadingError(
                    duplicate["product_code"], measurement.measurement_id
                )
            connection.execute(
                """INSERT INTO paint_readings(
                    reading_id,product_code,session_id,measurement_role,metallic_grain,notes,
                    measurement_id,measurement_guid,measurement_timestamp,measurement_name,
                    instrument_serial,angles_json,formula_json,created_at,schema_version,
                    measurement_fingerprint,quality_status,quality_issues_json,capture_context_json,
                    formula_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    reading_id, product.code, session_id, role, metallic_grain, notes.strip(),
                    measurement.measurement_id, measurement.guid,
                    measurement.timestamp.isoformat() if measurement.timestamp else measurement.timestamp_raw,
                    measurement.name, instrument_serial, json.dumps(angles),
                    json.dumps(formula_snapshot), created_at, PAINT_READING_SCHEMA_VERSION,
                    measurement_fingerprint, quality_status, json.dumps(quality_issues),
                    json.dumps(capture_context), formula_id,
                ),
            )
        return {
            "reading_id": reading_id, "product_code": product.code,
            "display_code": product.display_code, "description": product.description,
            "session_id": session_id, "measurement_role": role,
            "formula_id": formula_id,
            "metallic_grain": metallic_grain, "notes": notes.strip(),
            "measurement_id": measurement.measurement_id,
            "measurement_guid": measurement.guid,
            "instrument_serial": measurement.instrument_serial or "",
            "angles": angles, "created_at": created_at,
            "schema_version": PAINT_READING_SCHEMA_VERSION,
            "measurement_fingerprint": measurement_fingerprint,
            "quality_status": quality_status,
            "quality_issues": quality_issues,
            "capture_context": capture_context,
        }

    def readings(self, product_code: str) -> tuple[dict, ...]:
        product = self.get(product_code)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM paint_readings WHERE product_code=? ORDER BY created_at DESC",
                (product.code,),
            ).fetchall()
        return tuple({
            "reading_id": row["reading_id"], "product_code": product.code,
            "display_code": product.display_code, "description": product.description,
            "session_id": row["session_id"], "measurement_role": row["measurement_role"],
            "formula_id": row["formula_id"],
            "metallic_grain": row["metallic_grain"], "notes": row["notes"],
            "measurement_id": row["measurement_id"], "measurement_guid": row["measurement_guid"],
            "instrument_serial": row["instrument_serial"],
            "angles": json.loads(row["angles_json"]), "created_at": row["created_at"],
            "schema_version": row["schema_version"],
            "measurement_fingerprint": row["measurement_fingerprint"],
            "quality_status": row["quality_status"],
            "quality_issues": json.loads(row["quality_issues_json"]),
            "capture_context": json.loads(row["capture_context_json"]),
        } for row in rows)

    def training_records(self, *, eligible_only: bool = False) -> tuple[dict, ...]:
        clauses = "WHERE quality_status='eligible'" if eligible_only else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM paint_readings {clauses} ORDER BY created_at, reading_id"
            ).fetchall()
        return tuple({
            "schema": "mandacor.paint-spectrum.v1",
            "example_id": row["reading_id"],
            "group_key": row["product_code"],
            "features": {
                "spectrum_lab_multiangle": json.loads(row["angles_json"]),
                "metallic_grain": row["metallic_grain"],
                "capture_context": json.loads(row["capture_context_json"]),
            },
            "label": {
                "product_code": row["product_code"],
                "selected_formula_id": row["formula_id"],
                "formula_snapshot": json.loads(row["formula_json"]),
            },
            "provenance": {
                "session_id": row["session_id"],
                "measurement_role": row["measurement_role"],
                "measurement_id": row["measurement_id"],
                "measurement_guid": row["measurement_guid"],
                "measurement_timestamp": row["measurement_timestamp"],
                "instrument_serial": row["instrument_serial"],
                "created_at": row["created_at"],
                "measurement_fingerprint": row["measurement_fingerprint"],
            },
            "quality": {
                "status": row["quality_status"],
                "issues": json.loads(row["quality_issues_json"]),
                "source_schema_version": row["schema_version"],
            },
        } for row in rows)

    def spectral_matches(self, measurement, *, limit: int = 30) -> dict:
        """Compare a measurement with every paint reading and keep each product's best match."""
        query_angles = {
            int(angle): (value.L, value.a, value.b)
            for angle, value in measurement.angles.items()
        }
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.*, COUNT(DISTINCT v.id) AS formula_count,
                       (SELECT COUNT(*) FROM paint_readings count_reading
                        WHERE count_reading.product_code = p.code) AS reading_count,
                       r.reading_id AS matched_reading_id,
                       r.measurement_id AS matched_measurement_id,
                       r.angles_json AS matched_angles_json
                FROM paint_readings r
                JOIN products p ON p.code = r.product_code
                JOIN formula_variants v ON v.product_code = p.code
                WHERE p.deleted_at IS NULL
                GROUP BY r.reading_id
                """
            ).fetchall()

        best_by_product: dict[str, dict] = {}
        for row in rows:
            try:
                candidate = {
                    int(item["angle"]): (
                        float(item["l"]), float(item["a"]), float(item["b"])
                    )
                    for item in json.loads(row["matched_angles_json"])
                }
                if set(candidate) != set(query_angles):
                    continue
                squared_delta_e = 0.0
                for angle, query_lab in query_angles.items():
                    candidate_lab = candidate[angle]
                    squared_delta_e += sum(
                        (candidate_value - query_value) ** 2
                        for candidate_value, query_value in zip(candidate_lab, query_lab)
                    )
                delta_e_rms = math.sqrt(squared_delta_e / len(query_angles))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

            # A smooth, monotonic score: identical readings are 100%; increasing
            # multi-angle Delta E reduces compatibility without a hard cutoff.
            compatibility = 100.0 * math.exp(-delta_e_rms / 10.0)
            current = best_by_product.get(row["code"])
            if current is None or delta_e_rms < current["delta_e"]:
                best_by_product[row["code"]] = {
                    "product": self._product(row),
                    "compatibility": round(compatibility, 1),
                    "delta_e": round(delta_e_rms, 4),
                    "reading_id": row["matched_reading_id"],
                    "measurement_id": row["matched_measurement_id"],
                }

        ordered = sorted(
            best_by_product.values(),
            key=lambda item: (item["delta_e"], item["product"].description.casefold()),
        )
        return {"items": tuple(ordered[:limit]), "total": len(ordered)}

    @staticmethod
    def _group_code(system: str) -> str:
        return {"POLIESTER": "2", "ESMALTE_SINTETICO": "4", "LACA": "5", "PU": "6", "EPOXI": "E"}[system]

    @staticmethod
    def _system_label(system: str) -> str:
        return {"POLIESTER": "Poliéster", "ESMALTE_SINTETICO": "Esmalte sintético", "LACA": "Laca", "PU": "PU", "EPOXI": "Epóxi"}[system]

    @staticmethod
    def _paint_line(system: str) -> str:
        return {"POLIESTER": "SKYDUR", "ESMALTE_SINTETICO": "SKYLUX", "LACA": "SKYLAC", "PU": "SKYDUR", "EPOXI": "SKYFROTA"}[system]

    @staticmethod
    def _search_text(code: str, values: dict) -> str:
        return _normalized(" ".join((
            code, values["description"], values.get("year", ""),
            values.get("universal_code", ""), values.get("nuance", ""),
            values.get("manufacturer", ""), values.get("finish_label", ""),
        )))

    def _insert_product(self, connection: sqlite3.Connection, code: str, values: dict, *, origin: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """
            INSERT INTO products(
                code,description,year,universal_code,nuance,manufacturer_code,manufacturer,
                observations,group_code,system,system_label,paint_line,finish_code,finish_label,
                personalized,search_text,origin,modified_at,deleted_at
            ) VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, '', ?, 1, ?, ?, ?, NULL)
            """,
            (
                code, values["description"], values.get("year", ""),
                values.get("universal_code", ""), values.get("nuance", ""),
                values.get("manufacturer", ""), values.get("observations", ""),
                self._group_code(values["system"]), values["system"],
                self._system_label(values["system"]), self._paint_line(values["system"]),
                values.get("finish_label", ""), self._search_text(code, values), origin, now,
            ),
        )

    @staticmethod
    def _replace_variants(connection: sqlite3.Connection, code: str, variants: list[dict]) -> None:
        ids = [row[0] for row in connection.execute(
            "SELECT id FROM formula_variants WHERE product_code=?", (code,)
        )]
        if ids:
            connection.executemany("DELETE FROM formula_components WHERE formula_id=?", ((item,) for item in ids))
        connection.execute("DELETE FROM formula_variants WHERE product_code=?", (code,))
        now = datetime.now(timezone.utc).isoformat()
        for variant in variants:
            components = variant["components"]
            total = sum(float(item["weight_g"]) for item in components)
            cursor = connection.execute(
                "INSERT INTO formula_variants(product_code,condition,package,version,updated_at,total_weight_g) VALUES (?, ?, ?, ?, ?, ?)",
                (code, variant["condition"], variant.get("package", "1 Quarto"), int(variant.get("version", 1)), now, total),
            )
            connection.executemany(
                "INSERT INTO formula_components VALUES (?, ?, ?, ?, ?)",
                ((cursor.lastrowid, position, item["base_code"], item.get("base_name", ""), float(item["weight_g"])) for position, item in enumerate(components, 1)),
            )

    @staticmethod
    def _product(row: sqlite3.Row, variants: tuple[FormulaVariant, ...] = ()) -> FormulaProduct:
        return FormulaProduct(
            code=row["code"], display_code=formula_display_code(row["code"], row["system"]),
            description=row["description"], year=row["year"],
            universal_code=row["universal_code"], nuance=row["nuance"],
            manufacturer=row["manufacturer"], observations=row["observations"],
            system=row["system"], system_label=row["system_label"],
            paint_line=row["paint_line"], finish_code=row["finish_code"],
            finish_label=row["finish_label"],
            personalized=bool(row["personalized"]), formula_count=row["formula_count"],
            origin=row["origin"], reading_count=row["reading_count"],
            variants=variants,
        )
