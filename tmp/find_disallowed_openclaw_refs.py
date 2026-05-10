from pathlib import Path
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
root = Path(r"C:\Users\Veritas\.openclaw")
patterns = [r"openai/gpt-5\.5", r"chatgpt-5\.5", r"agentRuntime\.id\s*[:=]\s*[\"']codex[\"']", r"runtime\s*[:=]\s*[\"']codex[\"']"]
regexes = [re.compile(p, re.I) for p in patterns]
exclude_parts = {"node_modules", ".git", "dist", "media", "canvas", "agents", "sessions", "tasks", "logs", ".dreams"}
allowed_suffixes = {".md", ".json", ".txt", ".yaml", ".yml", ".bak", ".backup", ".last-good"}
for path in root.rglob('*'):
    if not path.is_file():
        continue
    if any(part in exclude_parts for part in path.parts):
        continue
    if path.suffix.lower() not in allowed_suffixes and path.name not in {'openclaw.json','openclaw.json.bak','openclaw.json.last-good'}:
        continue
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    hits=[]
    for i,line in enumerate(text.splitlines(),1):
        if any(rx.search(line) for rx in regexes):
            hits.append((i,line.strip()))
    if hits:
        print(f'FILE::{path}')
        for i,line in hits:
            print(f'{i}:{line}')
