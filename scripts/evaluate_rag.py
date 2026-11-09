"""Offline baseline: python -m scripts.evaluate_rag --output /tmp/rag-evaluation.json."""

import argparse
import json
from pathlib import Path

from cyberhub_manager.ai.evaluation import evaluate, load_questions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path(__file__).resolve().parents[1] / "tests/fixtures/ai/evaluation_questions.json")
    parser.add_argument("--min-similarity", type=float, default=0.2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(load_questions(args.questions), min_similarity=args.min_similarity)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
