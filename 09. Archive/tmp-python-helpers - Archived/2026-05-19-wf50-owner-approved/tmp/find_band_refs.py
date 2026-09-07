import pathlib
terms=['band-update','band update','band_refresh','apply_band_update','entry_band_fetch','band_note_sync','entry band']
paths=list(pathlib.Path('06. Playbooks').rglob('*.md'))+list(pathlib.Path('memory').rglob('*.md'))
for p in paths:
    s=p.read_text(encoding='utf-8',errors='ignore')
    if any(term.lower() in s.lower() for term in terms):
        print(p)
