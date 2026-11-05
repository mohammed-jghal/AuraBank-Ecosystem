"""Local RAG over policy documents: TF-IDF retrieval, stdlib only.

Choice (see ADR-002): in-memory TF-IDF over a handful of short policy
files. Cost $0, latency ~1ms, deterministic, no network, no vector-DB
account. It is the right store for 3 policy docs; it is the WRONG store
for 10,000 documents (that is when Pinecone/Chroma earns its cost).
Retrieval returns the top-k chunks with scores; a miss (score 0 for
every chunk) is reported as such so the orchestrator can fall back to
the default policy instead of hallucinating a rule.
"""
import math
import re
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text):
    return _TOKEN.findall(text.lower())


class PolicyStore:
    def __init__(self, policy_dir):
        self.policy_dir = Path(policy_dir)
        self.chunks = []  # list of {source, text, tokens}
        self._load()

    def _load(self):
        if not self.policy_dir.exists():
            return
        for path in sorted(self.policy_dir.glob("*.md")):
            text = path.read_text()
            # Split on blank lines / headings into retrievable chunks.
            for para in re.split(r"\n\s*\n", text):
                para = para.strip()
                if len(para) < 20:
                    continue
                self.chunks.append(
                    {"source": path.name, "text": para,
                     "tokens": _tokens(para)}
                )
        # Document frequency for IDF.
        df = {}
        for c in self.chunks:
            for t in set(c["tokens"]):
                df[t] = df.get(t, 0) + 1
        self._df = df
        self._n = max(len(self.chunks), 1)

    def _idf(self, token):
        return math.log((self._n + 1) / (self._df.get(token, 0) + 1)) + 1.0

    def retrieve(self, query, top_k=3):
        """Return list of {source, text, score}, best first. Empty on miss."""
        qtok = _tokens(query or "")
        if not qtok or not self.chunks:
            return []
        scored = []
        for c in self.chunks:
            tf = {}
            for t in c["tokens"]:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for t in set(qtok):
                if t in tf:
                    score += tf[t] * self._idf(t)
            # Normalise by chunk length so long chunks do not always win.
            score /= math.sqrt(len(c["tokens"]))
            if score > 0:
                scored.append({"source": c["source"], "text": c["text"],
                               "score": round(score, 4)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
