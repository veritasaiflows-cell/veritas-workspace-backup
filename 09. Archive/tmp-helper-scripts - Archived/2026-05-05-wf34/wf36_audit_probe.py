import json, sqlite3
conn = sqlite3.connect(r'tmp\workspace-index.sqlite')
out = {
  'tables': [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")],
  'fts_tables': [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'documents_fts%' ORDER BY name")],
  'meta': dict(conn.execute("SELECT key, value FROM meta ORDER BY key")),
  'docs_sample': conn.execute("SELECT path, domain, note_type FROM documents ORDER BY path LIMIT 10").fetchall(),
  'top_targets': conn.execute("SELECT target, link_type, COUNT(*) c FROM links GROUP BY target, link_type ORDER BY c DESC, target LIMIT 15").fetchall(),
  'heading_levels': conn.execute("SELECT level, COUNT(*) FROM headings GROUP BY level ORDER BY level").fetchall(),
  'domains': conn.execute("SELECT domain, COUNT(*) FROM documents GROUP BY domain ORDER BY COUNT(*) DESC LIMIT 15").fetchall(),
}
print(json.dumps(out, indent=2))
