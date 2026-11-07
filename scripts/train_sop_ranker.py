"""Train the SOP ranker: learn how to weigh the retrieval signals from labelled questions.

The hand-tuned ranker adds BM25, TF-IDF cosine, character 3-grams, term coverage and rule boosts with
weights picked by hand, and rejects out-of-scope questions with a word list written for the benchmark's
own negative questions. This script replaces both with a learned linear ranker (listwise / ListNet top-1):

* every (question, chunk) pair of the SOP corpus becomes one row of 16 features (the same signals);
* label 1 when the chunk answers the question (same rule as src/engine/sop_evaluation.py);
* a score threshold, chosen on training questions only, decides when to answer nothing.

Evaluation is grouped by question (a question never sits in both train and test):
  1. 5-fold cross-validation over all 100 labelled questions, repeated 10 times;
  2. train on the original 30-question benchmark only, test on the 70 held-out questions.

Usage:  python scripts/train_sop_ranker.py            (evaluate + write src/agent/multi_agent/sop_ranker.json)
        python scripts/train_sop_ranker.py --no-write (evaluate only)
Needs scikit-learn (offline only; the app reads the JSON weights with plain Python).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.multi_agent.repo_docs_agent import (  # noqa: E402
    SOP_RANKER_PATH, RepoDocsAgent, _normalize, heuristic_score)
from src.engine.sop_embeddings import embed_model, vectors_path  # noqa: E402

BENCHMARKS = {'original': ROOT / 'tests/fixtures/sop_retrieval_benchmark.json',
              'heldout': ROOT / 'tests/fixtures/sop_retrieval_heldout.json'}
FEATURES = ['bm25:log1p', 'tfidf_cos', 'trig_sim', 'coverage', 'code_exact', 'code_token', 'title_boost',
            'recipe_match', 'topping_rule', 'storage_match', 'storage_penalty', 'image_match',
            'phrase_exact', 'phrase_partial', 'is_full_table', 'is_log_row']
CATEGORY = 'SOP_QUY_CHUAN'


def relevant(chunk, case) -> bool:
    files, codes = set(case['expected_files']), set(case['expected_codes'])
    keywords = [_normalize(k) for k in case['expected_keywords']]
    text = _normalize(chunk.content + ' ' + chunk.title)
    return ((Path(chunk.file_path).name in files) if files else True) \
        and ((chunk.metadata.get('code') in codes) if codes else True) \
        and (any(k in text for k in keywords) if keywords else True)


def vectorize(f: dict) -> list[float]:
    out = []
    for name in FEATURES:
        base, _, kind = name.partition(':')
        v = float(f.get(base, 0.0))
        out.append(math.log1p(max(v, 0.0)) if kind == 'log1p' else v)
    return out


def build_rows(agent, cases):
    """Per question: feature matrix over every SOP chunk, labels, heuristic scores (with its cutoff)."""
    chunks = [(i, c) for i, c in enumerate(agent.chunks) if c.category == CATEGORY]
    data = []
    for case in cases:
        ctx = agent._query_context(case['query'], CATEGORY, scope_list=False)
        if ctx is None:
            data.append({'case': case, 'X': None, 'y': None, 'ids': None})
            continue
        scores = agent.bm25.get_scores(ctx['expanded_tokens'])
        X, y, ids, H = [], [], [], []
        for i, c in chunks:
            if ctx['explicit_codes'] and c.metadata.get('code') not in ctx['explicit_codes']:
                continue
            f = agent._components(ctx, c, float(scores[i]))
            X.append(vectorize(f))
            H.append(heuristic_score(f))
            y.append(int((not case['is_negative']) and relevant(c, case)))
            ids.append(i)
        data.append({'case': case, 'X': np.array(X), 'y': np.array(y), 'ids': ids, 'h': np.array(H)})
    return data


def candidates(row, k=300):
    """The chunks a question is trained on: every right answer plus the 300 the hand-tuned scorer likes most."""
    top = np.argsort(-row['h'])[:k]
    return np.unique(np.concatenate([top, np.flatnonzero(row['y'] == 1)]))


def fit(rows, seed=0, l2=0.01, iters=400, lr=0.1):
    """Listwise linear ranker (ListNet top-1): softmax over a question's candidates should put its probability
    mass on the right answers. Trained by gradient descent; negative questions only set the threshold."""
    answerable = [r for r in rows if r['X'] is not None and not r['case']['is_negative'] and r['y'].sum()]
    X = np.vstack([r['X'][candidates(r)] for r in answerable])
    mean, scale = X.mean(axis=0), X.std(axis=0)
    scale[scale < 1e-9] = 1.0
    lists = []
    for r in answerable:
        c = candidates(r)
        y = r['y'][c].astype(float)
        lists.append(((r['X'][c] - mean) / scale, y / y.sum()))
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        grad = l2 * w
        for Z, target in lists:
            s = Z @ w
            p = np.exp(s - s.max())
            p /= p.sum()
            grad += Z.T @ (p - target) / len(lists)
        w -= lr * grad
    return {'mean': mean, 'scale': scale, 'w': w, 'b': 0.0}


def score(model, X):
    return ((X - model['mean']) / model['scale']) @ model['w'] + model['b']


def ranked(model, row, threshold, k=5):
    if row['X'] is None:
        return []
    s = score(model, row['X'])
    order = np.argsort(-s)[:k]
    return [int(row['y'][j]) for j in order if s[j] >= threshold]


def metrics(results):
    """results: list of (is_negative, labels of returned top-5 in order)."""
    pos = [r for neg, r in results if not neg]
    negs = [r for neg, r in results if neg]

    def first(r):
        return next((i + 1 for i, v in enumerate(r) if v), None)
    ranks = [first(r) for r in pos]
    return {'Hit@1': 100 * np.mean([x == 1 for x in ranks]),
            'Hit@3': 100 * np.mean([x is not None and x <= 3 for x in ranks]),
            'Hit@5': 100 * np.mean([x is not None for x in ranks]),
            'MRR': float(np.mean([1 / x if x else 0 for x in ranks])),
            'Rejection': 100 * np.mean([len(r) == 0 for r in negs]) if negs else float('nan')}


def choose_threshold(model, rows):
    """Score cut-off that gets the most training questions right (answer at rank 1, or say nothing)."""
    tops = []
    for r in rows:
        if r['X'] is None:
            continue
        s = score(model, r['X'])
        j = int(np.argmax(s))
        tops.append((float(s[j]), r['case']['is_negative'], bool(r['y'][j])))
    candidates = sorted({t for t, _, _ in tops})
    best, best_t = -1, 0.0
    for i, t in enumerate(candidates):
        lo = candidates[i - 1] if i else t - 1
        cut = (lo + t) / 2
        ok = sum((top < cut) if neg else (top >= cut and good) for top, neg, good in tops)
        if ok > best:
            best, best_t = ok, cut
    return best_t


def evaluate_learned(train, test, seed=0):
    model = fit(train, seed)
    t = choose_threshold(model, train)
    return metrics([(r['case']['is_negative'], ranked(model, r, t)) for r in test])


def evaluate_heuristic(agent, cases):
    out = []
    for case in cases:
        hits = agent.search(case['query'], top_k=5, category_filter=CATEGORY)
        out.append((case['is_negative'], [int(relevant(type('C', (), {
            'content': h['content'], 'title': h['title'], 'file_path': h['file_path'], 'metadata': h['metadata']}),
            case)) for h in hits]))
    return metrics(out)


def summarize(runs):
    keys = runs[0].keys()
    return {k: (float(np.nanmean([r[k] for r in runs])), float(np.nanstd([r[k] for r in runs]))) for k in keys}


def fmt(m):
    def one(k, v):
        d = 3 if k == 'MRR' else 1
        return f'{k}={v[0]:.{d}f}±{v[1]:.{d}f}' if isinstance(v, tuple) else f'{k}={v:.{d}f}'
    return ' '.join(one(k, v) for k, v in m.items())


def cross_validate(rows, ids, by_id, repeats):
    runs = []
    for rep in range(repeats):
        shuffled = ids[:]
        random.Random(rep).shuffle(shuffled)
        folds = [shuffled[i::5] for i in range(5)]
        preds = []
        for k in range(5):
            test_ids = set(folds[k])
            tr = [by_id[i] for i in ids if i not in test_ids]
            te = [by_id[i] for i in ids if i in test_ids]
            model = fit(tr, seed=rep)
            t = choose_threshold(model, tr)
            preds += [(r['case']['is_negative'], ranked(model, r, t)) for r in te]
        runs.append(metrics(preds))
    return summarize(runs)


def dense_feature(vectors, query_vec):
    from src.agent.multi_agent.repo_docs_agent import dense_gap
    return np.array(dense_gap([None if d is None else float(d @ query_vec) for d in vectors]))


def with_dense(agent, rows):
    """Copy of the rows with one more feature: cosine between question and chunk embeddings (0 if not embedded)."""
    docs_path = vectors_path()
    q_path = docs_path.with_name(f'benchmark_queries_{embed_model()}.npz')
    if not (docs_path.exists() and q_path.exists()):
        return None
    d = np.load(docs_path)
    doc = dict(zip([str(i) for i in d['ids']], d['vectors'].astype(np.float32)))
    q = np.load(q_path)
    qv = dict(zip([str(i) for i in q['ids']], q['vectors'].astype(np.float32)))
    out = []
    for r in rows:
        if r['X'] is None:
            out.append(r)
            continue
        v = qv[r['case']['query_id']]
        cos = dense_feature([doc.get(agent.chunks[i].chunk_id) for i in r['ids']], v)
        out.append({**r, 'X': np.column_stack([r['X'], cos])})
    return out


def export(final, threshold, features, agent, extra=None):
    spec = {'model': 'listwise_linear', 'features': features,
            'mean': [round(float(x), 6) for x in final['mean']],
            'scale': [round(float(x), 6) for x in final['scale']],
            'weights': [round(float(x), 6) for x in final['w']], 'bias': round(final['b'], 6),
            'threshold': round(float(threshold), 6), 'corpus': agent.corpus_fingerprint(CATEGORY)}
    spec.update(extra or {})
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--repeats', type=int, default=10)
    args = ap.parse_args()

    import os
    os.environ['SOP_RANKER'] = 'heuristic'  # the baseline below must use the hand-tuned ranker
    agent = RepoDocsAgent(ROOT)
    cases = {name: json.loads(p.read_text(encoding='utf-8')) for name, p in BENCHMARKS.items()}
    every = cases['original'] + cases['heldout']
    rows = build_rows(agent, every)
    by_id = {r['case']['query_id']: r for r in rows}
    ids = [c['query_id'] for c in every]

    report = {'questions': {k: len(v) for k, v in cases.items()}}
    report['heuristic'] = {name: evaluate_heuristic(agent, c) for name, c in cases.items()}
    report['heuristic']['all'] = evaluate_heuristic(agent, every)
    report['learned_train_original_test_heldout'] = evaluate_learned(
        [by_id[c['query_id']] for c in cases['original']], [by_id[c['query_id']] for c in cases['heldout']])
    report[f'learned_cv5x{args.repeats}'] = cross_validate(rows, ids, by_id, args.repeats)
    final = fit(rows, seed=0)
    threshold = choose_threshold(final, rows)
    report['weights'] = {f: round(float(w), 3) for f, w in zip(FEATURES, final['w'])}

    dense_spec = None
    dense_rows = with_dense(agent, rows)
    if dense_rows is not None:
        d_by_id = {r['case']['query_id']: r for r in dense_rows}
        report[f'learned_semantic_cv5x{args.repeats}'] = cross_validate(dense_rows, ids, d_by_id, args.repeats)
        d_final = fit(dense_rows, seed=0)
        d_threshold = choose_threshold(d_final, dense_rows)
        report['weights_semantic'] = {f: round(float(w), 3) for f, w in zip(FEATURES + ['dense_cos'], d_final['w'])}
        dense_spec = export(d_final, d_threshold, FEATURES + ['dense_cos'], agent,
                            {'variant': 'semantic', 'embedding_model': embed_model()})

    for k, v in report.items():
        if k == 'heuristic':
            for name, m in v.items():
                print(f'{k}/{name}: {fmt(m)}')
        elif isinstance(v, dict) and k.startswith('learned'):
            print(f'{k}: {fmt(v)}')
        else:
            print(f'{k}: {v}')

    if not args.no_write:
        spec = export(final, threshold, FEATURES, agent,
                      {'variant': 'lexical', 'trained_on': {k: len(v) for k, v in cases.items()},
                       'evaluation': json.loads(json.dumps(report, default=lambda o: list(o) if isinstance(o, tuple) else str(o)))})
        if dense_spec:
            spec['dense'] = dense_spec
        SOP_RANKER_PATH.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
        print('wrote', SOP_RANKER_PATH.relative_to(ROOT))


if __name__ == '__main__':
    main()
