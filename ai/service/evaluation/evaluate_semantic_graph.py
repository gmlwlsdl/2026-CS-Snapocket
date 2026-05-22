"""Evaluate Snapocket retrieval and graph quality against a small golden set.

Usage:
  python ai/service/evaluation/evaluate_semantic_graph.py \
    --golden ai/service/evaluation/golden_set.example.json \
    --user-id <user-id> \
    --api-base http://127.0.0.1:18080 \
    --api-key <aiops-api-key> \
    --graph-db backend/snapocket_local.db
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib import request


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_5: float
    ndcg_at_10: float
    mrr_at_10: float


@dataclass(frozen=True)
class GraphMetrics:
    parent_precision: float
    parent_recall: float
    false_parent_rate: float
    cycle_count: int
    multi_parent_violations: int
    deleted_doc_edge_leaks: int


def _post_json(api_base: str, api_key: str, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["x-api-key"] = api_key
    req = request.Request(f"{api_base.rstrip('/')}{path}", method="POST", headers=headers, data=body)
    with request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(str(data.get("error") or data))
    return data.get("data") if isinstance(data.get("data"), dict) else {}


def _dcg(hits: list[int]) -> float:
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(hits))


def evaluate_retrieval(*, golden: dict, user_id: str, api_base: str, api_key: str) -> RetrievalMetrics:
    recall_scores: list[float] = []
    ndcg_scores: list[float] = []
    reciprocal_ranks: list[float] = []
    for item in golden.get("queries") or []:
        query = str(item.get("query") or "").strip()
        relevant = {str(doc_id) for doc_id in item.get("relevant_document_ids") or [] if str(doc_id).strip()}
        if not query or not relevant:
            continue
        data = _post_json(
            api_base,
            api_key,
            "/v1/search/semantic",
            {"query": query, "user_id": user_id, "limit": 10},
        )
        retrieved = [str(result.get("document_id") or "") for result in data.get("items") or []]
        top5 = retrieved[:5]
        hits10 = [1 if doc_id in relevant else 0 for doc_id in retrieved[:10]]
        recall_scores.append(len(set(top5) & relevant) / max(1, len(relevant)))
        ideal = [1] * min(len(relevant), 10)
        ndcg_scores.append((_dcg(hits10) / _dcg(ideal)) if ideal else 0.0)
        reciprocal_ranks.append(
            next((1.0 / rank for rank, doc_id in enumerate(retrieved[:10], start=1) if doc_id in relevant), 0.0)
        )
    count = max(1, len(recall_scores))
    return RetrievalMetrics(
        recall_at_5=round(sum(recall_scores) / count, 4),
        ndcg_at_10=round(sum(ndcg_scores) / count, 4),
        mrr_at_10=round(sum(reciprocal_ranks) / count, 4),
    )


def _active_parent_edges(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    return {
        (str(source), str(target))
        for source, target in conn.execute(
            """
            select source_document_id, target_document_id
            from graph_edges
            where status = 'active' and edge_type = 'parent_of'
            """
        )
    }


def _count_cycles(parent_edges: set[tuple[str, str]]) -> int:
    children_by_parent: dict[str, set[str]] = {}
    for parent, child in parent_edges:
        children_by_parent.setdefault(parent, set()).add(child)
    cycle_count = 0
    for start in children_by_parent:
        stack = [(start, set())]
        while stack:
            node, path = stack.pop()
            if node in path:
                cycle_count += 1
                break
            stack.extend((child, {*path, node}) for child in children_by_parent.get(node, set()))
    return cycle_count


def evaluate_graph(*, golden: dict, graph_db: Path) -> GraphMetrics:
    conn = sqlite3.connect(graph_db)
    try:
        parent_edges = _active_parent_edges(conn)
        expected_parent = {
            (str(item.get("parent")), str(item.get("child")))
            for item in (golden.get("graph") or {}).get("parent_pairs") or []
        }
        negative_pairs = {
            tuple(sorted((str(item.get("source")), str(item.get("target")))))
            for item in (golden.get("graph") or {}).get("negative_pairs") or []
        }
        parent_pairs_undirected = {tuple(sorted(pair)) for pair in parent_edges}
        false_parent_hits = len(parent_pairs_undirected & negative_pairs)
        children = [child for _parent, child in parent_edges]
        multi_parent_violations = len(children) - len(set(children))
        deleted_doc_edge_leaks = int(
            conn.execute(
                """
                select count(*)
                from graph_edges ge
                left join documents s on s.id = ge.source_document_id
                left join documents t on t.id = ge.target_document_id
                where ge.status = 'active' and (s.deleted_at is not null or t.deleted_at is not null)
                """
            ).fetchone()[0]
        )
    finally:
        conn.close()

    precision = len(parent_edges & expected_parent) / max(1, len(parent_edges))
    recall = len(parent_edges & expected_parent) / max(1, len(expected_parent))
    return GraphMetrics(
        parent_precision=round(precision, 4),
        parent_recall=round(recall, 4),
        false_parent_rate=round(false_parent_hits / max(1, len(negative_pairs)), 4),
        cycle_count=_count_cycles(parent_edges),
        multi_parent_violations=multi_parent_violations,
        deleted_doc_edge_leaks=deleted_doc_edge_leaks,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:18080")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--graph-db", required=True)
    args = parser.parse_args()

    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    result = {
        "retrieval": evaluate_retrieval(
            golden=golden,
            user_id=args.user_id,
            api_base=args.api_base,
            api_key=args.api_key,
        ).__dict__,
        "graph": evaluate_graph(golden=golden, graph_db=Path(args.graph_db)).__dict__,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
