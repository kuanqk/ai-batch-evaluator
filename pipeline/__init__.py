"""Processing pipeline: download → convert → extract → rubric → LLM."""

from pipeline.orchestrator import run_pipeline

__all__ = ["run_pipeline"]
