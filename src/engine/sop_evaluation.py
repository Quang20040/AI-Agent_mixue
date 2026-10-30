# -*- coding: utf-8 -*-
"""SOP and Recipe Retrieval Evaluation Engine.

Evaluates retrieval quality against ground-truth benchmarks:
- Hit@1, Hit@3, Hit@5
- MRR (Mean Reciprocal Rank)
- Precision@3
- Negative Query Rejection Rate (True Negative Rate for out-of-scope / missing queries)

Never sends documents to external embedding APIs without explicit permission.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agent.multi_agent.repo_docs_agent import RepoDocsAgent, _normalize

REPO_ROOT = Path(__file__).resolve().parents[2]


class SOPEvaluationEngine:
    def __init__(self, benchmark_path: Path | str | None = None, repo_dir: Path | str | None = None):
        self.repo_dir = Path(repo_dir) if repo_dir else REPO_ROOT
        self.benchmark_path = Path(benchmark_path) if benchmark_path else (self.repo_dir / "tests" / "fixtures" / "sop_retrieval_benchmark.json")
        self.agent = RepoDocsAgent(self.repo_dir)

    def load_benchmark(self) -> list[dict[str, Any]]:
        with open(self.benchmark_path, encoding="utf-8") as fp:
            return json.load(fp)

    def evaluate_case(self, case: dict[str, Any], top_k: int = 5) -> dict[str, Any]:
        query = case["query"]
        hits = self.agent.search(query, top_k=top_k, category_filter="SOP_QUY_CHUAN")

        is_negative = case.get("is_negative", False)
        if is_negative:
            # For negative / out-of-scope query, success means NO hits returned
            passed = len(hits) == 0
            return {
                "query_id": case["query_id"],
                "query": query,
                "is_negative": True,
                "passed": passed,
                "hits_count": len(hits),
                "rank": None,
                "hit_at_1": passed,
                "hit_at_3": passed,
                "hit_at_5": passed,
                "reciprocal_rank": 1.0 if passed else 0.0,
            }

        expected_codes = set(case.get("expected_codes", []))
        expected_files = set(case.get("expected_files", []))
        expected_keywords = [_normalize(k) for k in case.get("expected_keywords", [])]

        best_rank: int | None = None
        for rank, hit in enumerate(hits, start=1):
            hit_file = Path(hit.get("file_path", "")).name
            hit_code = hit.get("metadata", {}).get("code", "")
            content_norm = _normalize(hit.get("content", "") + " " + hit.get("title", ""))

            file_match = hit_file in expected_files if expected_files else True
            code_match = hit_code in expected_codes if expected_codes else True
            keyword_match = any(kw in content_norm for kw in expected_keywords) if expected_keywords else True

            # Hit is relevant if it matches file/code AND at least one expected keyword
            if file_match and code_match and keyword_match:
                if best_rank is None:
                    best_rank = rank
                    break

        hit_at_1 = best_rank == 1 if best_rank is not None else False
        hit_at_3 = best_rank is not None and best_rank <= 3
        hit_at_5 = best_rank is not None and best_rank <= 5
        rr = 1.0 / best_rank if best_rank is not None else 0.0

        return {
            "query_id": case["query_id"],
            "query": query,
            "is_negative": False,
            "passed": hit_at_3,
            "hits_count": len(hits),
            "rank": best_rank,
            "hit_at_1": hit_at_1,
            "hit_at_3": hit_at_3,
            "hit_at_5": hit_at_5,
            "reciprocal_rank": rr,
        }

    def run_evaluation(self, output_report_path: Path | str | None = None) -> dict[str, Any]:
        cases = self.load_benchmark()
        results = [self.evaluate_case(case) for case in cases]

        positive_cases = [r for r in results if not r["is_negative"]]
        negative_cases = [r for r in results if r["is_negative"]]

        n_pos = len(positive_cases)
        n_neg = len(negative_cases)

        hit_1 = sum(1 for r in positive_cases if r["hit_at_1"]) / n_pos if n_pos else 0.0
        hit_3 = sum(1 for r in positive_cases if r["hit_at_3"]) / n_pos if n_pos else 0.0
        hit_5 = sum(1 for r in positive_cases if r["hit_at_5"]) / n_pos if n_pos else 0.0
        mrr = sum(r["reciprocal_rank"] for r in positive_cases) / n_pos if n_pos else 0.0

        neg_rejected = sum(1 for r in negative_cases if r["hits_count"] == 0)
        neg_rejection_rate = neg_rejected / n_neg if n_neg else 0.0

        report = {
            "benchmark_cases_count": len(cases),
            "positive_cases_count": n_pos,
            "negative_cases_count": n_neg,
            "metrics": {
                "Hit@1": round(hit_1 * 100, 2),
                "Hit@3": round(hit_3 * 100, 2),
                "Hit@5": round(hit_5 * 100, 2),
                "MRR": round(mrr, 4),
                "Negative_Rejection_Rate_pct": round(neg_rejection_rate * 100, 2),
            },
            "cases": results,
        }

        if output_report_path:
            out_p = Path(output_report_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as fp:
                json.dump(report, fp, ensure_ascii=False, indent=2)

        return report


def evaluate_sop_retrieval(
    benchmark_path: Path | str | None = None,
    repo_dir: Path | str | None = None,
    output_report_path: Path | str | None = None
) -> dict[str, Any]:
    """Hàm tiện ích chạy đánh giá toàn diện năng lực truy xuất SOP/công thức."""
    evaluator = SOPEvaluationEngine(benchmark_path=benchmark_path, repo_dir=repo_dir)
    return evaluator.run_evaluation(output_report_path=output_report_path)


if __name__ == "__main__":
    rep = evaluate_sop_retrieval(output_report_path=REPO_ROOT / "data" / "agent_private" / "sop-retrieval-benchmark-report.json")
    print(json.dumps(rep["metrics"], indent=2))
