from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


class FormulaTrainingDatasetExporter:
    """Export versioned JSONL examples without inventing labels or data splits."""

    def export(self, catalog, output: Path, *, eligible_only: bool = True) -> dict:
        records = catalog.training_records(eligible_only=eligible_only)
        quality_counts = Counter(record["quality"]["status"] for record in records)
        output.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=output.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            try:
                for record in records:
                    line = json.dumps(
                        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ) + "\n"
                    stream.write(line)
                    digest.update(line.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, output)

        manifest = {
            "schema": "mandacor.paint-spectrum.manifest.v1",
            "record_schema": "mandacor.paint-spectrum.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "product_count": len({record["group_key"] for record in records}),
            "quality_counts": dict(sorted(quality_counts.items())),
            "eligible_only": eligible_only,
            "sha256": digest.hexdigest(),
            "split_policy": "group by group_key/product_code; never split readings of one color across train and validation",
            "warning": "Formula spectra and adjustment-effect trials are different tasks; do not infer pigment dosage from this file alone.",
        }
        manifest_path = output.with_suffix(output.suffix + ".manifest.json")
        manifest_text = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=manifest_path.parent, delete=False
        ) as stream:
            temporary_manifest = Path(stream.name)
            stream.write(manifest_text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_manifest, manifest_path)
        return {**manifest, "output": str(output), "manifest": str(manifest_path)}
