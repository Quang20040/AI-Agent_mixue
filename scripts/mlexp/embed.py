"""Embed the SOP chunks and benchmark questions with a few multilingual sentence encoders (experiment only)."""
import json, sys, time
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

here = Path(__file__).parent
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
data = json.loads((here / 'corpus.json').read_text(encoding='utf-8'))
docs = [c['text'] for c in data['chunks']]
queries = [q['text'] for q in data['queries']]
MODELS = {
    'e5-small': ('intfloat/multilingual-e5-small', 'query: ', 'passage: '),
    'e5-base': ('intfloat/multilingual-e5-base', 'query: ', 'passage: '),
    'minilm': ('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', '', ''),
}
log = {}
for name, (repo, qp, dp) in MODELS.items():
    t = time.time()
    m = SentenceTransformer(repo, device='cpu')
    m.max_seq_length = 256
    D = m.encode([dp + d for d in docs], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    t_doc = time.time() - t
    t = time.time()
    Q = m.encode([qp + q for q in queries], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    t_q = (time.time() - t) / len(queries)
    np.savez_compressed(out / f'{name}.npz', D=D.astype(np.float16), Q=Q.astype(np.float16))
    log[name] = {'repo': repo, 'dim': int(D.shape[1]), 'doc_seconds': round(t_doc, 1), 'query_ms': round(1000 * t_q, 1),
                 'params_m': round(sum(p.numel() for p in m.parameters()) / 1e6, 1)}
    print(name, log[name], flush=True)
(out / 'log.json').write_text(json.dumps(log, indent=1))
(out / 'ids.json').write_text(json.dumps({'chunks': [c['i'] for c in data['chunks']], 'queries': [q['id'] for q in data['queries']]}))
