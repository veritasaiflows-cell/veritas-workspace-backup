"""Latency probe for the workspace derived semantic-memory index.

Read-only. Times, against the real engine:
  1. vmi.search_index() end-to-end per query (embed + vector search)
  2. raw ollama embed latency for the same text (splits embed vs search cost)
  3. FTS keyword query latency
  4. store facts: size, table row counts, vec table schema
No --write, no rebuild; require_fresh=False (cache validated fresh today 19:46).
"""
from __future__ import annotations
import json, os, sqlite3, statistics, sys, time, urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Veritas\.openclaw\workspace")
sys.path.insert(0, str(ROOT / "scripts"))
import vector_memory_index as vmi  # noqa: E402

DB = ROOT / "tmp" / "vector-memory.sqlite"
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text:latest")

QUERIES = [
    "finance alerts and recommendations OS pivot",
    "WF74 recursive self-improvement loop",
    "semantic memory vector drift validation",
    "Randall durable goals and communication preferences",
]


def embed_ms(text: str) -> tuple[float, dict]:
    payload = json.dumps({"model": MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/embeddings", data=payload,
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    return (time.perf_counter() - t0) * 1000.0, body


def stats(xs: list[float]) -> dict:
    return {"n": len(xs), "min_ms": round(min(xs), 1),
            "median_ms": round(statistics.median(xs), 1),
            "max_ms": round(max(xs), 1)}


def main() -> None:
    out: dict = {"db": str(DB), "db_size_mb": round(os.path.getsize(DB) / 1e6, 2),
                 "ollama_url": OLLAMA, "embed_model": MODEL}

    con = sqlite3.connect(DB)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute(
        "select name from sqlite_master where type='table' order by name").fetchall()]
    counts: dict = {}
    for t in tables:
        try:
            counts[t] = cur.execute(f'select count(*) from "{t}"').fetchone()[0]
        except Exception as e:
            counts[t] = f"err {e}"
    out["tables"] = counts

    vec_info: dict = {}
    for vt in [t for t in tables if t.endswith("_vec")]:
        try:
            cols = [r[1] for r in cur.execute(f"pragma table_info('{vt}')")]
            row = cur.execute(f"select * from '{vt}' limit 1").fetchone()
            vec_info[vt] = {
                "cols": cols,
                "sample_types": [type(x).__name__ for x in row] if row else None,
                "sample_lens": [len(x) if isinstance(x, (bytes, str, list)) else None
                                for x in row] if row else None,
            }
        except Exception as e:
            vec_info[vt] = f"err {e}"
    out["vec_schema"] = vec_info

    fts_tables = [t for t in tables if "fts" in t.lower()]
    if fts_tables:
        ft = fts_tables[0]
        samples = []
        for _ in range(3):
            t0 = time.perf_counter()
            cur.execute(f"select rowid from {ft} where {ft} match ? limit 8",
                        ("alert OR workflow",))
            cur.fetchall()
            samples.append((time.perf_counter() - t0) * 1000)
        out["fts_latency_ms"] = stats(samples)
    con.close()

    out["embed_latency_ms"] = stats([embed_ms(QUERIES[2])[0] for _ in range(3)])

    results = []
    for q in QUERIES:
        t0 = time.perf_counter()
        payload = vmi.search_index(root=ROOT, db_path=DB, query=q, limit=8,
                                   ollama_url=OLLAMA, timeout=30,
                                   require_fresh=False)
        dt = (time.perf_counter() - t0) * 1000
        hits = payload.get("results") or payload.get("hits") or []
        results.append({"query": q, "ms": round(dt, 1),
                        "status": payload.get("status"), "hits": len(hits)})
    out["search_end_to_end"] = results
    out["search_ms_stats"] = stats([r["ms"] for r in results])

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()