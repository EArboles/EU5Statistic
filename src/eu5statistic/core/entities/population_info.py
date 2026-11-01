from dataclasses import dataclass


@dataclass
class PopulationInfo:
    """Information on a single population (POP) in conservation"""

    culture: int | None = None
    religion: int | None = None
    size: int | None = None
    literacy: float = 0.0
    estate: str | None = None
