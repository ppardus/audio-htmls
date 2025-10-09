#!/usr/bin/env python3
"""
Build per-engine HTML pages listing audio samples from CSVs.

What it does:
- Scans all CSV files under a given folder (recursively).
- Reads rows (LANG, ENGINE, VOICE, GENDER, FILENAME).
- Finds matching audio files (.aac/.acc/.m4a) anywhere under the folder.
- Writes one HTML per ENGINE at the folder root: azure.html, aws.html, gcp.html, etc.
- Also writes index.html linking to each engine page.

Usage:
  python build_audio_pages.py /path/to/shared/folder
  # or, from inside the folder:
  python build_audio_pages.py .
"""
import sys, csv, html, datetime
from pathlib import Path
from collections import defaultdict

AUDIO_EXTS = {'.aac', '.acc', '.m4a'}  # handles both .aac and the .acc typo

def norm(s): return (s or '').strip()

def scan_audio_files(root: Path):
    """Index all audio files by lowercase basename -> relative POSIX path."""
    mapping = {}
    duplicates = defaultdict(list)
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            key = p.name.lower()
            rel = p.relative_to(root).as_posix()
            if key in mapping:
                duplicates[key].append(rel)
            else:
                mapping[key] = rel
    return mapping, duplicates

def find_csvs(root: Path):
    return list(root.rglob('*.csv'))

def read_rows_from_csv(csv_path: Path, root: Path):
    rows = []
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows
        # normalize header names (case/space-insensitive)
        field_map = { (k or '').strip().lower(): k for k in reader.fieldnames }
        def get(row, key): return norm(row.get(field_map.get(key, key), ''))
        for i, r in enumerate(reader, start=2):  # header is line 1
            rows.append({
                'source_csv': csv_path.relative_to(root).as_posix(),
                'rownum': i,
                'lang':   get(r, 'lang'),
                'engine': get(r, 'engine'),
                'voice':  get(r, 'voice'),
                'gender': get(r, 'gender'),
                'filename': get(r, 'filename'),
            })
    return rows

def resolve_audio_path(root: Path, filename: str, audio_index: dict):
    """Return (relpath, exists_bool) for the audio file."""
    if not filename:
        return filename, False

    p = root / filename
    if p.exists() and p.is_file():
        return p.relative_to(root).as_posix(), True

    base = Path(filename).name.lower()
    if base in audio_index:
        return audio_index[base], True

    # Try same basename with alternate extensions
    stem = Path(filename).stem
    for ext in AUDIO_EXTS:
        candidate = (stem + ext).lower()
        if candidate in audio_index:
            return audio_index[candidate], True

    return filename, False

def make_html(engine: str, entries: list, out_path: Path):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    total = len(entries)
    found = sum(1 for e in entries if e['exists'])
    missing = total - found

    css = """
    body { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; margin: 24px; }
    header { display:flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
    h1 { margin: 0; }
    .counts { color: #555; }
    .search { margin-top: 12px; }
    input[type="search"] { padding: 8px 10px; width: 320px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; margin-top: 20px; }
    .card { border: 1px solid #e2e2e2; border-radius: 14px; padding: 12px 14px; }
    .meta { font-size: 14px; color: #555; }
    .filename { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: #333; }
    .missing { border-color: #ffd7d7; background: #fff7f7; }
    .missing strong { color: #b50000; }
    audio { width: 100%; margin-top: 8px; }
    footer { margin-top: 28px; font-size: 12px; color: #666; }
    """
    js = """
    function filterCards(el){
      const q = (el.value || '').toLowerCase();
      document.querySelectorAll('.card').forEach(c=>{
        const hay = (c.getAttribute('data-hay') || '').toLowerCase();
        c.style.display = hay.includes(q) ? '' : 'none';
      });
    }
    """

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(engine)} — Audio Index</title>
<style>{css}</style>
</head>
<body>
<header>
  <h1>{html.escape(engine)}</h1>
  <div class="counts">{total} rows • {found} files found • {missing} missing</div>
</header>
<div class="search">
  <input type="search" placeholder="Filter (lang, voice, gender, filename)..." oninput="filterCards(this)" />
</div>
<div class="grid">
"""]

    for e in entries:
        hay = ' '.join([
            e.get('lang',''), e.get('voice',''), e.get('gender',''), e.get('filename','')
        ])
        meta = f"{html.escape(e.get('lang',''))} — {html.escape(e.get('voice',''))} ({html.escape(e.get('gender',''))})"
        fn_disp = html.escape(e.get('filename',''))
        rel = html.escape(e.get('relpath','') or '')
        if e['exists']:
            card = f"""<div class="card" data-hay="{html.escape(hay)}">
  <div class="meta">{meta}</div>
  <div class="filename">{fn_disp}</div>
  <audio controls preload="none" src="{rel}" type="audio/aac">
    Your browser does not support the <code>audio</code> element.
  </audio>
</div>"""
        else:
            card = f"""<div class="card missing" data-hay="{html.escape(hay)}">
  <div class="meta">{meta}</div>
  <div class="filename">{fn_disp}</div>
  <p><strong>Missing file:</strong> {fn_disp}</p>
</div>"""
        parts.append(card)

    parts.append(f"""</div>
<footer>Generated on {now}. Source CSV rows combined per engine.</footer>
<script>{js}</script>
</body>
</html>""")
    out_path.write_text('\n'.join(parts), encoding='utf-8')

def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    print(f"[i] Root folder: {root}")

    audio_index, dupes = scan_audio_files(root)
    print(f"[i] Indexed {len(audio_index)} audio file(s).")
    if dupes:
        print(f"[!] Duplicate basenames detected ({len(dupes)}). Using first seen; others noted.")

    csvs = find_csvs(root)
    if not csvs:
        print("[!] No CSV files found under the root.")
        return 2
    print(f"[i] Found {len(csvs)} CSV file(s).")

    # Load rows from all CSVs
    rows = []
    for c in csvs:
        rows.extend(read_rows_from_csv(c, root))
    print(f"[i] Read {len(rows)} row(s) total.")

    # Group by engine and resolve audio paths
    by_engine = defaultdict(list)
    for r in rows:
        engine = r.get('engine') or 'unknown'
        rel, exists = resolve_audio_path(root, r.get('filename',''), audio_index)
        r['relpath'], r['exists'] = rel, exists
        by_engine[engine].append(r)

    # Emit per-engine HTML at the root
    summary = []
    for engine, entries in sorted(by_engine.items(), key=lambda kv: kv[0].lower()):
        entries.sort(key=lambda e: (e.get('lang',''), e.get('voice',''), e.get('filename','')))
        out_path = root / f"{engine.lower()}.html"
        make_html(engine, entries, out_path)
        found = sum(1 for e in entries if e['exists'])
        missing = len(entries) - found
        print(f"[+] Wrote {out_path.name}: {len(entries)} rows, {found} ok, {missing} missing")
        summary.append((engine, out_path.name, len(entries), found, missing))

    # Small index.html
    idx = ["<!doctype html><html><head><meta charset='utf-8'><title>Audio Engines</title></head><body><h1>Audio Engines</h1><ul>"]
    for engine, name, total, found, missing in summary:
        idx.append(f"<li><a href='{html.escape(name)}'>{html.escape(engine)}</a> — {total} rows, {found} ok, {missing} missing</li>")
    idx.append("</ul></body></html>")
    (root / "index.html").write_text("\n".join(idx), encoding='utf-8')
    print("[+] Wrote index.html")
    return 0

if __name__ == "__main__":
    from pathlib import Path
    sys.exit(main())
