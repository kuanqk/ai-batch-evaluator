"""Parse CSV file_path into structured fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedPath:
    program: str
    city: str
    trainer: str
    group_name: str
    file_name: str


def parse_file_path(file_path: str) -> ParsedPath:
    """
    Path format: [0]/[1:city]/[2:trainer]/[3:group]/[4:file]
    Backslashes normalized to forward slashes.
    """
    normalized = file_path.replace("\\", "/").strip().strip("/")
    parts = [p for p in normalized.split("/") if p]
    if len(parts) < 5:
        raise ValueError(
            f"file_path must have at least 5 segments (program/city/trainer/group/file), got {len(parts)}"
        )
    return ParsedPath(
        program=parts[0],
        city=parts[1],
        trainer=parts[2],
        group_name=parts[3],
        file_name="/".join(parts[4:]),
    )
