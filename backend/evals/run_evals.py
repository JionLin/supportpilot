"""Run SupportPilot eval cases against a real LLM and write report.md.

Usage:
  export LLM_API_KEY=...
  uv run python -m evals.run_evals

This script intentionally refuses to invent metrics. Without a real API key
it exits with instructions and does not overwrite evals/report.md with fake scores.

@author jiaolin
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.agent.graph import run_agent
from app.config import get_settings
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)

CASES_PATH = Path(__file__).resolve().parent / "cases.yaml"
REPORT_PATH = Path(__file__).resolve().parent / "report.md"


def load_cases() -> list[dict[str, Any]]:
    """Load eval cases from YAML.

    Returns:
        list[dict[str, Any]]: Case definitions.
    """
    raw = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list):
        msg = f"Invalid cases file: {CASES_PATH}"
        raise ValueError(msg)
    return cases


def _tools_from_reply(reply_actions: list[Any]) -> set[str]:
    names: set[str] = set()
    for action in reply_actions:
        tool = getattr(action, "tool", None) or (
            action.get("tool") if isinstance(action, dict) else None
        )
        if tool:
            names.add(str(tool))
    return names


async def run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Execute one eval case with the real configured LLM.

    Args:
        case: Case definition.

    Returns:
        dict[str, Any]: Per-case result row.
    """
    message = str(case["message"])
    _, reply, state = await run_agent(
        message=message,
        session_factory=get_session_factory(),
    )
    used_tools = _tools_from_reply(reply.actions)
    expected_tools = set(case.get("expected_tools") or [])
    tools_ok = expected_tools.issubset(used_tools) if expected_tools else True
    intent_ok = reply.intent == case.get("expected_intent")
    requires_citations = bool(case.get("requires_citations"))
    citations_ok = (len(reply.citations) > 0) if requires_citations else True
    passed = intent_ok and tools_ok and citations_ok
    return {
        "id": case.get("id"),
        "passed": passed,
        "intent_ok": intent_ok,
        "expected_intent": case.get("expected_intent"),
        "actual_intent": reply.intent,
        "tools_ok": tools_ok,
        "expected_tools": sorted(expected_tools),
        "actual_tools": sorted(used_tools),
        "citations_ok": citations_ok,
        "citation_count": len(reply.citations),
        "needs_human": reply.needs_human,
        "answer_preview": reply.answer[:200],
        "status": state.get("status"),
    }


def render_report(
    *,
    results: list[dict[str, Any]],
    model: str,
    base_url: str,
) -> str:
    """Render Markdown report from real run results.

    Args:
        results: Per-case results.
        model: Model name used.
        base_url: LLM base URL.

    Returns:
        str: Markdown report content.
    """
    total = len(results)
    passed = sum(1 for row in results if row["passed"])
    rate = (passed / total * 100.0) if total else 0.0
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# SupportPilot Eval Report",
        "",
        f"- Date: {now}",
        f"- Model: `{model}`",
        f"- LLM base URL: `{base_url}`",
        f"- Cases: {total}",
        f"- Passed: {passed}/{total} ({rate:.1f}%)",
        "",
        "| ID | Pass | Intent | Tools | Citations | Preview |",
        "|---|---|---|---|---|---|",
    ]
    for row in results:
        lines.append(
            "| {id} | {passed} | {intent} | {tools} | {cites} | {preview} |".format(
                id=row["id"],
                passed="yes" if row["passed"] else "no",
                intent=f"{row['expected_intent']}→{row['actual_intent']}",
                tools=",".join(row["actual_tools"]) or "-",
                cites=row["citation_count"],
                preview=(row["answer_preview"] or "").replace("|", "/"),
            )
        )
    lines.append("")
    lines.append(
        "_Numbers above come only from this real run. Do not copy invented metrics._"
    )
    lines.append("")
    return "\n".join(lines)


async def async_main(*, write_report: bool) -> int:
    """Run all cases when a real API key is configured.

    Args:
        write_report: Whether to write evals/report.md.

    Returns:
        int: Process exit code.
    """
    settings = get_settings()
    if not settings.llm_api_key:
        print(
            "LLM_API_KEY is not set. Refusing to run evals or write fabricated "
            "scores into evals/report.md.\n"
            "Set LLM_API_KEY (and optionally LLM_BASE_URL / LLM_MODEL), then re-run:\n"
            "  uv run python -m evals.run_evals"
        )
        placeholder = REPORT_PATH
        if not placeholder.exists():
            placeholder.write_text(
                "# SupportPilot Eval Report\n\n"
                "> No real eval run has been executed yet.\n>\n"
                "> Results must come from `uv run python -m evals.run_evals` "
                "with a real `LLM_API_KEY`. Do not invent pass rates or metrics.\n",
                encoding="utf-8",
            )
        return 2

    cases = load_cases()
    results: list[dict[str, Any]] = []
    for case in cases:
        logger.info("Running case %s", case.get("id"))
        results.append(await run_case(case))

    report = render_report(
        results=results,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
    if write_report:
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"Wrote {REPORT_PATH}")
    print(report)
    failed = sum(1 for row in results if not row["passed"])
    return 1 if failed else 0


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run SupportPilot evals")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print report to stdout without writing report.md",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(async_main(write_report=not args.no_write)))


if __name__ == "__main__":
    main()
