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


def render_markdown(data: dict) -> str:
    env = data.get("environment", "?").upper()
    threshold = data.get("threshold") or 0.80
    views = data.get("views", {})
    all_passed = data.get("all_passed", False)

    # If the query returned nothing (empty views), make that explicit instead
    # of misleading readers with a "0% / 0 views" table.
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
    header_icon = "PASSED" if all_passed else "ATTENTION"
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

    # Footer
    lines.append("")
    passing = sum(1 for v in views.values() if v.get("status") == "PASS")
    failing = sum(1 for v in views.values() if v.get("status") == "FAIL")
    total = len(views)
    lines.append(
        f"Summary: **{passing} PASS**, **{failing} FAIL**, {total - passing - failing} no-data  "
        f"(out of {total} semantic views)"
    )
    lines.append("")
    lines.append(
        "_Note: SV eval is advisory. Platform flakiness on Cortex Analyst "
        "(`Invocation failed`) is auto-retried once; remaining failures "
        "are reported here. The blocking SV gate is "
        "`detect_sv_drift --fail-on-drift` in the dbt Quality Gate._"
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
