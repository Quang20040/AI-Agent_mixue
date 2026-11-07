"""Embed the SOP / recipe / rule chunks (and the benchmark questions) with the Gemini embedding API.

Run once when the SOP documents change; needs GEMINI_API_KEY in the environment (CI secret).
Day-by-day log rows (sales, purchases, stock counts, waste) are not embedded and never sent.
Writes data/sop_embeddings/<model>.npz and data/sop_embeddings/benchmark_queries_<model>.npz.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('SOP_RANKER', 'heuristic')

from src.agent.multi_agent.repo_docs_agent import LOG_TABLES, RepoDocsAgent  # noqa: E402
from src.engine.sop_embeddings import embed_model, embed_texts, vectors_path  # noqa: E402


def main():
    key = (os.environ.get('GEMINI_API_KEY') or '').strip()  # pasted secrets often end with a newline
    if not key:
        sys.exit('GEMINI_API_KEY is not set')
    agent = RepoDocsAgent(ROOT)
    chunks = [c for c in agent.chunks if c.category == 'SOP_QUY_CHUAN' and not c.file_path.endswith(LOG_TABLES)]
    docs = embed_texts([c.content[:6000] for c in chunks], 'RETRIEVAL_DOCUMENT', key,
                       titles=[c.title[:200] for c in chunks])
    out = vectors_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, ids=np.array([c.chunk_id for c in chunks]), vectors=docs.astype(np.float16),
                        model=embed_model(), corpus=agent.corpus_fingerprint('SOP_QUY_CHUAN'))
    cases = []
    for name in ('sop_retrieval_benchmark.json', 'sop_retrieval_heldout.json'):
        cases += json.loads((ROOT / 'tests' / 'fixtures' / name).read_text(encoding='utf-8'))
    qv = embed_texts([c['query'] for c in cases], 'RETRIEVAL_QUERY', key)
    np.savez_compressed(out.with_name(f'benchmark_queries_{embed_model()}.npz'),
                        ids=np.array([c['query_id'] for c in cases]), vectors=qv.astype(np.float16))
    print(f'{len(chunks)} chunks and {len(cases)} questions embedded with {embed_model()} -> {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
