"""Smoke tests for eval case loading (no real LLM).

@author jiaolin
"""

from __future__ import annotations

from pathlib import Path

import yaml
from evals.run_evals import CASES_PATH, load_cases


def test_cases_yaml_has_twenty_five_entries() -> None:
    """cases.yaml must define 25 evaluation prompts."""
    cases = load_cases()
    assert len(cases) == 25
    for case in cases:
        assert "id" in case
        assert "message" in case
        assert "expected_intent" in case
        assert "expected_tools" in case
        assert "requires_citations" in case


def test_report_placeholder_has_no_invented_metrics() -> None:
    """Placeholder report must not contain fabricated pass rates."""
    report = Path(__file__).resolve().parents[1] / "evals" / "report.md"
    text = report.read_text(encoding="utf-8")
    assert "No real eval run" in text
    assert "100%" not in text
    assert "Passed:" not in text


def test_cases_yaml_parses() -> None:
    """Raw YAML remains a mapping with a cases list."""
    raw = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert isinstance(raw["cases"], list)
