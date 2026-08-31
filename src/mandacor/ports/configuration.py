from __future__ import annotations

from typing import Protocol

from mandacor.config import InstrumentConnectionConfig


class ConfigurationRepository(Protocol):
    def load(self) -> InstrumentConnectionConfig: ...

    def save(self, config: InstrumentConnectionConfig) -> None: ...

