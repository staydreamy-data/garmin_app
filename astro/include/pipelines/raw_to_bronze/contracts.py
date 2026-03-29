from dataclasses import dataclass

@dataclass(frozen=True)
class TransformResult:
    asset: str
    files_seen: int
    rows_valid: int
    rows_invalid: int
    staged_files: int