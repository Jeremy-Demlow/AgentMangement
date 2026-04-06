"""Compute metrics from agent evaluation results and check thresholds.

Reads eval result JSON files, computes aggregate scores per metric,
classification metrics (precision, recall, F1), and checks against
environment-specific thresholds.

Usage:
    python -m agent_management.compute_metrics --env prod --results agent-evaluation/results/resort_executive_20260401_173852.json
    python -m agent_management.compute_metrics --env prod --results-dir agent-evaluation/results/
    python -m agent_management.compute_metrics --env dev --results-dir agent-evaluation/results/ --strict

Implements REQ-004: Evaluation Framework.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_management.utils.config import get_thresholds, load_env_config


def load_results(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def compute_scores(data: dict) -> dict[str, dict]:
    if "summary" in data and data["summary"]:
        return {
            metric: {"avg": info["avg"], "n": info["n"]}
            for metric, info in data["summary"].items()
        }

    scores: dict[str, list[float]] = {}
    for r in data.get("results", []):
        metric = r.get("metric_name", "unknown")
        score = r.get("eval_agg_score")
        if score is not None:
            scores.setdefault(metric, []).append(float(score))

    return {
        metric: {"avg": sum(vals) / len(vals), "n": len(vals)}
        for metric, vals in scores.items()
    }


def compute_classification_metrics(
    data: dict, thresholds: dict
) -> dict[str, dict]:
    results_list = data.get("results", [])
    if not results_list:
        return {}

    per_metric: dict[str, list[float]] = {}
    for r in results_list:
        metric = r.get("metric_name", "unknown")
        score = r.get("eval_agg_score")
        if score is not None:
            per_metric.setdefault(metric, []).append(float(score))

    classification = {}
    for metric, scores in per_metric.items():
        threshold = thresholds.get(metric)
        if threshold is None:
            continue
        tp = sum(1 for s in scores if s >= threshold)
        fn = sum(1 for s in scores if s < threshold)
        total = len(scores)
        precision = tp / total if total > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        classification[metric] = {
            "tp": tp,
            "fn": fn,
            "total": total,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return classification


def check_thresholds(scores: dict[str, dict], thresholds: dict) -> list[dict]:
    failures = []
    for metric, threshold in thresholds.items():
        if metric.startswith("sv_"):
            continue
        if metric not in scores:
            continue
        avg = scores[metric]["avg"]
        if avg < threshold:
            failures.append({
                "metric": metric,
                "score": avg,
                "threshold": threshold,
                "delta": avg - threshold,
            })
    return failures


def main():
    parser = argparse.ArgumentParser(description="Compute agent eval metrics")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--results", "-r", help="Single result JSON file")
    parser.add_argument("--results-dir", "-d", help="Directory of result JSON files")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any threshold failure")
    args = parser.parse_args()

    config = load_env_config(args.env)
    thresholds = get_thresholds(config)

    result_files = []
    if args.results:
        result_files = [Path(args.results)]
    elif args.results_dir:
        result_files = sorted(Path(args.results_dir).glob("*.json"))
    else:
        default_dir = Path(__file__).resolve().parent.parent / "agent-evaluation" / "results"
        result_files = sorted(default_dir.glob("*.json"))

    if not result_files:
        print("No result files found")
        sys.exit(1)

    print(f"Environment: {config['environment']}")
    print(f"Thresholds: {thresholds}")
    print(f"Files: {len(result_files)}")
    print("=" * 60)

    any_failure = False
    for path in result_files:
        data = load_results(path)
        agent = data.get("agent", path.stem)
        scores = compute_scores(data)
        classification = compute_classification_metrics(data, thresholds)

        print(f"\n{agent}:")
        for metric, info in sorted(scores.items()):
            threshold = thresholds.get(metric)
            status = ""
            if threshold is not None:
                if info["avg"] >= threshold:
                    status = f"  PASS (>= {threshold})"
                else:
                    status = f"  FAIL (< {threshold})"
                    any_failure = True
            print(f"  {metric}: {info['avg']:.4f} (n={info['n']}){status}")

            cls = classification.get(metric)
            if cls:
                print(f"    F1={cls['f1']:.4f}  Precision={cls['precision']:.4f}  "
                      f"Recall={cls['recall']:.4f}  (TP={cls['tp']} FN={cls['fn']})")

        failures = check_thresholds(scores, thresholds)
        if failures:
            print(f"  THRESHOLD FAILURES: {len(failures)}")
        else:
            print(f"  All thresholds passed")

    print(f"\n{'=' * 60}")
    if any_failure:
        print("RESULT: FAIL — one or more metrics below threshold")
        if args.strict:
            sys.exit(1)
    else:
        print("RESULT: PASS — all metrics meet thresholds")


if __name__ == "__main__":
    main()
