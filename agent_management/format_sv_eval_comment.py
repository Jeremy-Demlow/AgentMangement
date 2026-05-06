"""Format SV eval scores as a markdown PR comment.

Consumes JSON output from `get_sv_eval_scores --json` and writes a markdown
table to the given path (default /tmp/sv_eval_summary.md) that validate-pr.yml
posts back to the PR.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_THRESHOLD = 0.80

# Outcome statuses emitted by ``get_sv_eval_scores``. Anything not in this set
# blocks ``PASSED`` and is surfaced explicitly in the comment footer so the
# reader is not misled by hidden defaults.
PASS_STATUSES = {"PASS"}
FAIL_STATUSES = {"FAIL"}
ERROR_STATUSES = {"error"}
NO_RUN_STATUSES = {"no_run"}
EMPTY_STATUSES = {"empty"}


def _row_status(entry: dict) -> str:
    status = entry.get("status", "?")
    if status == "PASS":
        return "PASS"
    if status == "FAIL":
        return "FAIL"
    if status == "no_run":
        return "NO RUN"
    if status == "empty":
        return "NO DATA"
    if status == "error":
        return "ERROR"
    return status


def _coalesce_threshold(value) -> float:
    """Return ``value`` if it is a real number, else the default.

    Avoids the ``data.get("threshold") or DEFAULT`` idiom which silently
    swaps an explicit ``0.0`` with the default. Truthfulness over brevity.
    """
    return value if isinstance(value, (int, float)) else DEFAULT_THRESHOLD


def _derive_all_passed(views: dict) -> bool:
    """Truthful ``all_passed`` regardless of the producer's default.

    A run is only PASSED when every recorded view is PASS. ERROR/NO_RUN/
    NO_DATA/FAIL all block PASSED; an empty view dict is also not PASSED.
    """
    if not views:
        return False
    return all(v.get("status") in PASS_STATUSES for v in views.values())


def _classify_header(views: dict, all_passed: bool) -> str:
    """Return the header word matching the actual fleet outcome."""
    if not views:
        return "NO DATA"
    if all_passed:
        return "PASSED"
    statuses = [v.get("status") for v in views.values()]
    if any(s in FAIL_STATUSES for s in statuses):
        return "FAILED"
    if any(s in ERROR_STATUSES for s in statuses):
        return "ERRORED"
    if any(s in NO_RUN_STATUSES | EMPTY_STATUSES for s in statuses):
        return "INCOMPLETE"
    return "ATTENTION"


def render_markdown(data: dict) -> str:
    env = (data.get("environment") or "?").upper()
    threshold = _coalesce_threshold(data.get("threshold"))
    views = data.get("views") or {}

    # Re-derive ``all_passed`` locally so the renderer is not at the mercy of
    # an upstream default like ``all_passed = True``. The producer's value is
    # advisory; the views dict is truth.
    producer_all_passed = data.get("all_passed")
    all_passed = _derive_all_passed(views)
    if isinstance(producer_all_passed, bool) and producer_all_passed != all_passed:
        # The producer disagrees with the data. Trust the data.
        all_passed = all_passed and producer_all_passed

    if not views:
        return (
            f"### Semantic View Evaluation Summary ({env}) — NO DATA\n\n"
            f"Threshold: **{threshold * 100:.0f}%** sql_correctness\n\n"
            f"_No SV eval results were returned for this run. This usually "
            f"means the run-name lookup missed the just-completed run "
            f"(observability log indexing lag) or the eval step itself "
            f"failed. Check the `Run SV evaluations` and `Collect SV eval "
            f"scores` step logs for details._\n"
        )

    lines: list[str] = []
    header_icon = _classify_header(views, all_passed)
    lines.append(f"### Semantic View Evaluation Summary ({env}) — {header_icon}")
    lines.append("")
    lines.append(f"Threshold: **{threshold * 100:.0f}%** sql_correctness")
    lines.append("")
    lines.append("| Semantic View | Status | Score | Scored | Errors | Run |")
    lines.append("| :--- | :--- | ---: | ---: | ---: | :--- |")

    for sv_name in sorted(views):
        v = views[sv_name]
        status = _row_status(v)
        score = v.get("score")
        score_str = f"{score * 100:.1f}%" if isinstance(score, (int, float)) else "—"
        scored = v.get("scored", "—")
        errors = v.get("errors", 0) or 0
        run = v.get("run_name", "—")
        # Truncate long run names
        if isinstance(run, str) and len(run) > 40:
            run = run[:37] + "…"
        lines.append(
            f"| `{sv_name}` | {status} | {score_str} | {scored} | {errors} | `{run}` |"
        )

    # Footer with distinct buckets so reviewers can tell PASS/FAIL/ERROR/
    # NO_RUN/NO_DATA apart at a glance.
    lines.append("")
    statuses = [v.get("status") for v in views.values()]
    passing = sum(1 for s in statuses if s in PASS_STATUSES)
    failing = sum(1 for s in statuses if s in FAIL_STATUSES)
    errored = sum(1 for s in statuses if s in ERROR_STATUSES)
    no_run = sum(1 for s in statuses if s in NO_RUN_STATUSES)
    no_data = sum(1 for s in statuses if s in EMPTY_STATUSES)
    total = len(views)
    lines.append(
        f"Summary: **{passing} PASS**, **{failing} FAIL**, **{errored} ERROR**, "
        f"**{no_run} NO RUN**, **{no_data} NO DATA**  (out of {total} semantic views)"
    )
    lines.append("")
    lines.append(
        "_Header reflects worst observed outcome. Threshold-fail and lookup-error "
        "both block PASSED. Cortex Analyst platform flakes (`Invocation failed`) "
        "surface as ERROR rows; the structural drift gate "
        "(`detect_sv_drift --fail-on-drift` in the dbt Quality Gate) remains the "
        "separate blocking check on source-vs-deployed coherence._"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Format SV eval JSON as markdown PR comment")
    ap.add_argument("--input", required=True, help="Path to get_sv_eval_scores --json output")
    ap.add_argument(
        "--output",
        default="/tmp/sv_eval_summary.md",
        help="Output markdown path (default: /tmp/sv_eval_summary.md)",
    )
    args = ap.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"ERROR: input not found: {path}", file=sys.stderr)
        return 1
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        print(f"ERROR: failed to parse {path}: {exc}", file=sys.stderr)
        return 1

    markdown = render_markdown(data)
    out_path = Path(args.output)
    out_path.write_text(markdown)
    print(f"Wrote {out_path} ({len(markdown)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
