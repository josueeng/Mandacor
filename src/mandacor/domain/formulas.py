from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FormulaComponent:
    position: int
    base_code: str
    base_name: str
    weight_g: float


@dataclass(frozen=True, slots=True)
class FormulaVariant:
    formula_id: int
    condition: str
    package: str
    version: int
    updated_at: str
    total_weight_g: float
    components: tuple[FormulaComponent, ...]


@dataclass(frozen=True, slots=True)
class FormulaProduct:
    code: str
    display_code: str
    description: str
    year: str
    universal_code: str
    nuance: str
    manufacturer: str
    observations: str
    system: str
    system_label: str
    paint_line: str
    finish_code: str
    finish_label: str
    personalized: bool
    formula_count: int
    origin: str = "SKYMIX"
    reading_count: int = 0
    variants: tuple[FormulaVariant, ...] = ()


@dataclass(frozen=True, slots=True)
class FormulaSearchResult:
    items: tuple[FormulaProduct, ...]
    total: int
    limit: int
    offset: int
