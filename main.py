#!/usr/bin/env python3
"""
Build per-language HTML pages listing audio samples from CSVs (combined across engines).

Updates (Oct 2025):
- Display human language NAMES instead of codes (e.g., "English (United States)" instead of "en-US") on index and detail pages.
- De-duplicate entries by VOICE within a language (keep one; prefer an entry with an existing audio file).
- Add gender filter chips (like the existing engine chips).
- Hide CSV source and filename from cards (cleaner UI).
- Make the entire row clickable on index page (not just the language title).

What it does:
- Scans all CSV files under a given folder (recursively).
- Reads rows with headers (case/space-insensitive): LANG, ENGINE, VOICE, GENDER, FILENAME.
- Indexes matching audio files (.aac/.acc/.m4a) anywhere under the folder.
- Writes one HTML per LANGUAGE CODE at the folder root: en-US.html, af-ZA.html, etc.
  Each language page displays the language NAME prominently, and includes entries from ALL engines (azure/aws/gcp/etc.) for that language,
  with filter chips for engine and gender + a search box.
- Also writes index.html linking to each language page, with quick stats.

Usage:
  python build_audio_pages.py /path/to/shared/folder
  # or, from inside the folder:
  python build_audio_pages.py .
"""
import sys, csv, html, datetime
from pathlib import Path
from collections import defaultdict, Counter

AUDIO_EXTS = {'.aac', '.acc', '.m4a'}  # handles both .aac and the .acc typo

# === Language code -> human-friendly name mapping (from product spec) ===
CODE_TO_NAME = {
    'sq-AL':'Albanian','am-ET':'Amharic','ar-DZ':'Arabic (Algeria)','ar-BH':'Arabic (Bahrain)',
    'ar-EG':'Arabic (Egypt)','ar-IQ':'Arabic (Iraq)','ar-JO':'Arabic (Jordan)','ar-KW':'Arabic (Kuwait)',
    'ar-LB':'Arabic (Lebanon)','ar-LY':'Arabic (Libya)','ar-MA':'Arabic (Morocco)','ar-OM':'Arabic (Oman)',
    'ar-QA':'Arabic (Qatar)','ar-SA':'Arabic (Saudi Arabia)','ar-SY':'Arabic (Syria)','ar-TN':'Arabic (Tunisia)',
    'ar-AE':'Arabic (United Arab Emirates)','ar-YE':'Arabic (Yemen)','hy-AM':'Armenian','bs-BA':'Bosnian',
    'bg-BG':'Bulgarian','my-MM':'Burmese','ca-ES':'Catalan','zh-CN':'Chinese (China)','zh-HK':'Chinese (Hong Kong SAR China)',
    'zh-TW':'Chinese (Taiwan)','hr-HR':'Croatian','cs-CZ':'Czech','da-DK':'Danish','nl-BE':'Dutch (Belgium)',
    'nl-NL':'Dutch (Netherlands)','en-AU':'English (Australia)','en-CA':'English (Canada)','en-HK':'English (Hong Kong SAR China)',
    'en-IN':'English (India)','en-IE':'English (Ireland)','en-KE':'English (Kenya)','en-NZ':'English (New Zealand)',
    'en-NG':'English (Nigeria)','en-PH':'English (Philippines)','en-SG':'English (Singapore)','en-ZA':'English (South Africa)',
    'en-TZ':'English (Tanzania)','en-GB':'English (United Kingdom)','en-US':'English (United States)','et-EE':'Estonian',
    'fi-FI':'Finnish','fr-BE':'French (Belgium)','fr-CA':'French (Canada)','fr-FR':'French (France)','fr-CH':'French (Switzerland)',
    'ka-GE':'Georgian','de-AT':'German (Austria)','de-DE':'German (Germany)','de-CH':'German (Switzerland)','el-GR':'Greek',
    'gu-IN':'Gujarati','he-IL':'Hebrew','hi-IN':'Hindi','hu-HU':'Hungarian','is-IS':'Icelandic','id-ID':'Indonesian',
    'ga-IE':'Irish','it-IT':'Italian','ja-JP':'Japanese','kn-IN':'Kannada','kk-KZ':'Kazakh','ko-KR':'Korean',
    'lv-LV':'Latvian','lt-LT':'Lithuanian','mk-MK':'Macedonian','ms-MY':'Malay','ml-IN':'Malayalam','mr-IN':'Marathi',
    'mn-MN':'Mongolian','nb-NO':'Norwegian','fa-IR':'Persian','pl-PL':'Polish','pt-BR':'Portuguese','pa-IN':'Punjabi',
    'ro-RO':'Romanian','ru-RU':'Russian','sr-Latn-RS':'Serbian','sk-SK':'Slovak','sl-SI':'Slovenian','so-SO':'Somali',
    'es-AR':'Spanish (Argentina)','es-BO':'Spanish (Bolivia)','es-CL':'Spanish (Chile)','es-CO':'Spanish (Colombia)',
    'es-CR':'Spanish (Costa Rica)','es-CU':'Spanish (Cuba)','es-DO':'Spanish (Dominican Republic)','es-EC':'Spanish (Ecuador)',
    'es-SV':'Spanish (El Salvador)','es-GQ':'Spanish (Equatorial Guinea)','es-GT':'Spanish (Guatemala)','es-HN':'Spanish (Honduras)',
    'es-MX':'Spanish (Mexico)','es-NI':'Spanish (Nicaragua)','es-PA':'Spanish (Panama)','es-PY':'Spanish (Paraguay)',
    'es-PE':'Spanish (Peru)','es-PR':'Spanish (Puerto Rico)','es-ES':'Spanish (Spain)','es-US':'Spanish (United States)',
    'es-UY':'Spanish (Uruguay)','es-VE':'Spanish (Venezuela)','sw-KE':'Swahili (Kenya)','sw-TZ':'Swahili (Tanzania)',
    'sv-SE':'Swedish','ta-IN':'Tamil (India)','ta-MY':'Tamil (Malaysia)','ta-SG':'Tamil (Singapore)','ta-LK':'Tamil (Sri Lanka)',
    'te-IN':'Telugu','th-TH':'Thai','tr-TR':'Turkish','uk-UA':'Ukrainian','ur-IN':'Urdu (India)','ur-PK':'Urdu (Pakistan)',
    'vi-VN':'Vietnamese','cy-GB':'Welsh','cmn-CN':'Mandarin Chinese',
    'cmn-TW':'Mandarin Chinese (Taiwan)',
    'wuu-CN':'Wu Chinese (China)',
    'yue-CN':'Cantonese (China)',
    'yue-HK':'Cantonese (Hong Kong)',
    'zh-CN-guangxi':'Chinese (Guangxi, China)',
    'zh-CN-henan':'Chinese (Henan, China)',
    'zh-CN-liaoning':'Chinese (Liaoning, China)',
    'zh-CN-shaanxi':'Chinese (Shaanxi, China)',
    'zh-CN-shandong':'Chinese (Shandong, China)',
    'zh-CN-sichuan':'Chinese (Sichuan, China)',

    'af-ZA':'Afrikaans (South Africa)',
    'ar-XA':'Arabic (Gulf)',
    'as-IN':'Assamese (India)',
    'az-AZ':'Azerbaijani (Azerbaijan)',
    'bn-BD':'Bengali (Bangladesh)',
    'bn-IN':'Bengali (India)',
    'en-GB-WLS':'English (United Kingdom — Wales)',
    'eu-ES':'Basque (Spain)',
    'fil-PH':'Filipino (Philippines)',
    'gl-ES':'Galician (Spain)',
    'iu-Cans-CA':'Inuktitut (Syllabics, Canada)',
    'iu-Latn-CA':'Inuktitut (Latin, Canada)',
    'jv-ID':'Javanese (Indonesia)',
    'km-KH':'Khmer (Cambodia)',
    'lo-LA':'Lao (Laos)',
    'mt-MT':'Maltese (Malta)',
    'ne-NP':'Nepali (Nepal)',
    'or-IN':'Odia (India)',
    'ps-AF':'Pashto (Afghanistan)',
    'pt-PT':'Portuguese (Portugal)',
    'si-LK':'Sinhala (Sri Lanka)',
    'sr-RS':'Serbian (Serbia)',
    'su-ID':'Sundanese (Indonesia)',
    'uz-UZ':'Uzbek (Uzbekistan)',
    'yue-HK':'Cantonese (Hong Kong)',
    'zu-ZA':'Zulu (South Africa)'
}



def norm(s):
    return (s or '').strip()


def scan_audio_files(root: Path):
    """Index all audio files by lowercase basename -> relative POSIX path. Track duplicates."""
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
                'lang':   get(r, 'lang') or 'unknown',
                'engine': get(r, 'engine') or 'unknown',
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


def engine_slug(e: str) -> str:
    return (e or 'unknown').strip().lower()


def lang_name(code: str) -> str:
    code = (code or '').strip()
    # Direct mapping first
    if code in CODE_TO_NAME:
        return CODE_TO_NAME[code]
    # Handle extended Chinese regional variants like zh-CN-henan, zh-CN-sichuan, etc.
    parts = code.split('-')
    if len(parts) >= 3 and parts[0].lower() == 'zh' and parts[1].upper() == 'CN':
        region = '-'.join(parts[2:]).replace('_', ' ').title()
        return f"Chinese ({region}, China)"
    # Fallback to the code itself
    return code or 'unknown'


def dedupe_by_voice(entries: list):
    """Within a language, keep only one entry per (normalized) voice.
    Preference order: entries with an existing audio file first; then stable order.
    """
    out = []
    seen = set()
    # Sort: exists first (False -> True flip), then deterministic tie-breakers
    entries_sorted = sorted(entries, key=lambda e: (not e.get('exists', False), engine_slug(e.get('engine','')), e.get('voice','') or '', e.get('filename','') or ''))
    for e in entries_sorted:
        v = norm(e.get('voice','')).lower()
        if v:
            if v in seen:
                continue
            seen.add(v)
        out.append(e)
    return out


def clean_voice(lang_code: str, voice: str) -> str:
    v = (voice or '').strip()
    if not v:
        return '(no voice)'
    code = (lang_code or '').strip()
    # Strip repeated leading '<code>-' prefixes, e.g., 'af-ZA-af-ZA-AdriNeural' -> 'AdriNeural'
    lower_prefix = (code + '-').lower()
    while v.lower().startswith(lower_prefix):
        v = v[len(code) + 1:]
    return v or '(no voice)'


def make_language_html(lang_code: str, entries: list, out_path: Path):
    """
    Build a single language page with entries from all engines.
    Includes:
      - Sticky search
      - Engine filter chips
      - Gender filter chips
      - Responsive cards
      - Missing-state styling
    """
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    total = len(entries)
    found = sum(1 for e in entries if e['exists'])
    missing = total - found

    # Engine & gender stats
    engines = sorted({engine_slug(e['engine']) for e in entries})
    genders = sorted({(e.get('gender') or '').strip().lower() for e in entries if e.get('gender')})

    per_engine_counts = Counter(engine_slug(e['engine']) for e in entries)
    per_engine_found = Counter(engine_slug(e['engine']) for e in entries if e['exists'])

    per_gender_counts = Counter((e.get('gender') or '').strip().lower() for e in entries if e.get('gender'))
    per_gender_found = Counter((e.get('gender') or '').strip().lower() for e in entries if e.get('gender') and e['exists'])

    display_lang = lang_name(lang_code)

    # Inline CSS (no external deps)
    css = """
    :root {
      --bg: #0b0f14;
      --panel: #0f151d;
      --card: #141b24;
      --text: #e6edf3;
      --muted: #9aa6b2;
      --border: #223043;
      --danger-bg: #2a1212;
      --danger-border: #5a1b1b;
      --danger-text: #ffb3b3;
      --chip-bg: #1a2430;
      --chip-on: #0e7afe;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Apple Color Emoji", "Segoe UI Emoji"; }
    a { color: #7cc4ff; text-decoration: none; }
    a:hover { text-decoration: underline; }

    .wrap { max-width: 1200px; margin: 0 auto; padding: 24px; }
    header { display:flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
    h1 { margin: 0; font-size: 28px; letter-spacing: 0.3px; }
    .counts { color: var(--muted); font-size: 14px; }
    .pill { display:inline-block; padding:.1rem .5rem; border:1px solid var(--border); border-radius: 999px; margin-left:8px; color: var(--muted); font-size:12px; }

    .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 14px; position: sticky; top: 0; z-index: 50; }

    .toolbar { display: grid; grid-template-columns: 1fr; gap: 10px; }
    @media (min-width: 760px) { .toolbar { grid-template-columns: 1fr auto; align-items: center; } }

    .search { display:flex; gap: 10px; }
    input[type="search"] {
      padding: 10px 12px; width: 100%;
      border-radius: 12px; border: 1px solid var(--border); background: var(--card); color: var(--text);
    }
    .chips { display:flex; flex-wrap: wrap; gap: 8px; }
    .chips + .chips { margin-top: 10px; }
    .chip {
      border: 1px solid var(--border); background: var(--chip-bg); color: var(--text);
      padding: 6px 10px; border-radius: 999px; font-size: 13px; cursor: pointer; user-select: none;
    }
    .chip.active { outline: 2px solid var(--chip-on); }
    .chip .k { opacity: .7; margin-left: 6px; font-variant-numeric: tabular-nums; }

    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; margin-top: 16px; }
    .card {
      border: 1px solid var(--border); border-radius: 14px; padding: 12px; background: var(--card);
    }
    .card.missing { border-color: var(--danger-border); background: var(--danger-bg); color: var(--danger-text); }
    .meta { font-size: 14px; color: var(--muted); display:flex; align-items:center; gap: 6px; flex-wrap: wrap; }
    .engine {
      padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid var(--border);
      background: #112235;
    }
    .engine[data-engine="aws"]   { background:#0f2a1e; }
    .engine[data-engine="azure"] { background:#10263b; }
    .engine[data-engine="gcp"]   { background:#251f0c; }
    .engine[data-engine="unknown"] { background:#2a2139; }
    .title { font-size: 16px; margin: 8px 0 4px 0; }
    audio { width: 100%; margin-top: 8px; border-radius: 8px; }
    footer { margin: 22px 0 8px; color: var(--muted); font-size: 12px; text-align: center; }
    .legend { color: var(--muted); font-size: 12px; margin-top: 8px; }
    """

    js = f"""
    const STATE = {{
      engines: new Set(), // empty = all on
      genders: new Set(), // empty = all on
      query: ''
    }};

    function applyFilters() {{
      const q = STATE.query.toLowerCase();
      const engineActive = STATE.engines;
      const genderActive = STATE.genders;
      const cards = document.querySelectorAll('.card');
      let visible = 0;
      cards.forEach(c => {{
        const hay = (c.getAttribute('data-hay') || '').toLowerCase();
        const eng = c.getAttribute('data-engine');
        const gen = (c.getAttribute('data-gender') || '').toLowerCase();
        const enginePass = (engineActive.size === 0) || engineActive.has(eng);
        const genderPass = (genderActive.size === 0) || genderActive.has(gen);
        const searchPass = !q || hay.includes(q);
        const show = enginePass && genderPass && searchPass;
        c.style.display = show ? '' : 'none';
        if (show) visible++;
      }});
      const total = cards.length;
      document.querySelector('#visibleCount').textContent = visible + "/" + total + " visible";
    }}

    function onSearch(el) {{
      STATE.query = el.value || '';
      applyFilters();
    }}

    function toggleEngine(el, eng) {{
      if (STATE.engines.has(eng)) {{
        STATE.engines.delete(eng);
        el.classList.remove('active');
      }} else {{
        STATE.engines.add(eng);
        el.classList.add('active');
      }}
      applyFilters();
    }}

    function clearEngines() {{
      STATE.engines.clear();
      document.querySelectorAll('.engine-chip').forEach(ch => ch.classList.remove('active'));
      applyFilters();
    }}

    function toggleGender(el, g) {{
      if (STATE.genders.has(g)) {{
        STATE.genders.delete(g);
        el.classList.remove('active');
      }} else {{
        STATE.genders.add(g);
        el.classList.add('active');
      }}
      applyFilters();
    }}

    function clearGenders() {{
      STATE.genders.clear();
      document.querySelectorAll('.gender-chip').forEach(ch => ch.classList.remove('active'));
      applyFilters();
    }}

    /* NEW: ensure only one audio plays at a time */
    document.addEventListener('play', function onAnyAudioPlay(e) {{
      const target = e.target;
      if (!(target && target.tagName === 'AUDIO')) return;
      document.querySelectorAll('audio').forEach(a => {{
        if (a !== target && !a.paused) a.pause();
      }});
    }}, true); // capture = true ensures we catch play events from <audio>

    window.addEventListener('DOMContentLoaded', applyFilters);
    """

    # Build page
    parts = [f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{html.escape(display_lang)} — Audio Index</title>
<style>{css}</style>
</head>
<body>
<div class=\"wrap\">
  <header>
    <h1>{html.escape(display_lang)} <span class=\"pill\">{html.escape(lang_code)}</span> <span class=\"pill\">{found} files • {missing} missing • {total} rows</span></h1>
    <div class=\"counts\" id=\"visibleCount\"></div>
  </header>

  <div class=\"panel\">
    <div class=\"toolbar\">
      <div class=\"search\">
        <input id=\"q\" type=\"search\" placeholder=\"Search voice, engine, gender…\" oninput=\"onSearch(this)\" />
      </div>
      <div>
        <div class=\"chips\" role=\"group\" aria-label=\"Filter by engine\">"""]

    # Engine filter chips
    for eng in engines:
        count = per_engine_counts.get(eng, 0)
        ok = per_engine_found.get(eng, 0)
        chip = f"""<div class=\"chip engine-chip\" onclick=\"toggleEngine(this, '{html.escape(eng)}')\" title=\"Toggle {html.escape(eng)}\">{html.escape(eng)} <span class=\"k\">{ok}/{count}</span></div>"""
        parts.append(chip)

    parts.append("""</div>""")

    # Gender filter chips
    parts.append("""<div class=\"chips\" role=\"group\" aria-label=\"Filter by gender\">""")
    for g in genders:
        count = per_gender_counts.get(g, 0)
        ok = per_gender_found.get(g, 0)
        label = g or 'unknown'
        parts.append(f"""<div class=\"chip gender-chip\" onclick=\"toggleGender(this, '{html.escape(g)}')\" title=\"Toggle {html.escape(label)}\">{html.escape(label)} <span class=\"k\">{ok}/{count}</span></div>""")
    parts.append("""</div>""")

    parts.append("""
    </div>
    <div class=\"legend\">Tip: click chips to toggle; use the search box to filter further.</div>
  </div>

  <div class=\"grid\">\n""")

    # Cards (no filename or CSV source shown)
    for e in entries:
        hay = ' '.join([
            e.get('engine',''), e.get('voice',''), e.get('gender','')
        ])
        meta_bits = []
        eng = engine_slug(e.get('engine',''))
        meta_bits.append(f"<span class='engine' data-engine='{html.escape(eng)}'>{html.escape(e.get('engine',''))}</span>")
        g = (e.get('gender') or '').strip()
        if g:
            meta_bits.append(html.escape(g))
        meta = " • ".join(meta_bits)

        title = lang_code + "-" + clean_voice(lang_code, e.get('voice'))
        exists = e['exists']
        gender_attr = (e.get('gender') or '').strip().lower()
        rel = html.escape(e.get('relpath','') or '')

        if exists:
            card = f"""<div class=\"card\" data-hay=\"{html.escape(hay)}\" data-engine=\"{html.escape(eng)}\" data-gender=\"{html.escape(gender_attr)}\">\n  <div class=\"meta\">{meta}</div>\n  <div class=\"title\">{html.escape(title)}</div>\n  <audio controls preload=\"none\" src=\"{rel}\" type=\"audio/aac\">\n    Your browser does not support the <code>audio</code> element.\n  </audio>\n</div>"""
        else:
            card = f"""<div class=\"card missing\" data-hay=\"{html.escape(hay)}\" data-engine=\"{html.escape(eng)}\" data-gender=\"{html.escape(gender_attr)}\">\n  <div class=\"meta\">{meta}</div>\n  <div class=\"title\">{html.escape(title)}</div>\n  <p><strong>Missing audio file</strong></p>\n</div>"""
        parts.append(card)

    parts.append(f"""</div>
  <footer>Generated on {html.escape(now)}. Combined all engines for {html.escape(display_lang)}.</footer>
</div>
<script>{js}</script>
</body>
</html>""")
    out_path.write_text('\n'.join(parts), encoding='utf-8')


def make_index_html(root: Path, summary_by_lang, dupes):
    """Small index with per-language links and quick stats. Whole row is clickable."""
    css = """
    :root{ --bg:#0b0f14; --panel:#0f151d; --text:#e6edf3; --muted:#9aa6b2; --border:#223043; --card:#141b24; }
    html,body{margin:0;background:var(--bg);color:var(--text);font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial;}
    a{color:#7cc4ff;text-decoration:none;} a:hover{text-decoration:underline;}
    .wrap{max-width:900px;margin:0 auto;padding:24px;}
    h1{margin:0 0 10px 0;}
    .panel{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:16px;}
    ul{list-style:none;padding:0;margin:0;}
    li{margin:8px 0;}
    .row{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px;color:inherit;text-decoration:none;}
    .row:hover{outline:2px solid #0e7afe;}
    .stats{color:var(--muted);font-size:13px;}
    .dupe{font-size:12px;color:#ffb3b3;}
    """
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    parts = ["""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Audio Languages</title><style>""", css, """</style></head><body>
<div class=\"wrap\">
<h1>Audio Languages</h1>
<div class=\"panel\">
<ul>"""]
    for lang_code, data in summary_by_lang:
        display = lang_name(lang_code)
        name = data['file']
        total = data['total']; found = data['found']; missing = data['missing']
        engines = ", ".join(sorted(data['engines']))
        parts.append(
            f"<li><a class='row' href='{html.escape(name)}'><div><strong>{html.escape(display)}</strong> <span class='stats'>({html.escape(lang_code)})</span></div>"
            f"<div class='stats'>{found} files • {missing} missing • {total} rows • engines: {html.escape(engines)}</div></a></li>"
        )
    parts.append("</ul></div>")

    # Duplicate basename note (if any)
    if dupes:
        n = sum(len(v) for v in dupes.values())
        parts.append(f"<p class='dupe'>Note: duplicate audio basenames detected ({len(dupes)} names, {n} extra occurrences). "
                     "The first encountered file was used for linking. Consider deduping.</p>")

    parts.append(f"<p class='stats'>Generated on {html.escape(now)}.</p>")
    parts.append("</div></body></html>")
    (root / "index.html").write_text("".join(parts), encoding='utf-8')


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

    # Resolve audio paths and group by LANGUAGE (combine all engines per language)
    by_lang = defaultdict(list)
    for r in rows:
        rel, exists = resolve_audio_path(root, r.get('filename',''), audio_index)
        r['relpath'], r['exists'] = rel, exists
        lang_code = r.get('lang') or 'unknown'
        by_lang[lang_code].append(r)

    # De-duplicate by voice within each language (keep one; prefer existing files)
    for lang_code, entries in by_lang.items():
        by_lang[lang_code] = dedupe_by_voice(entries)

    # Emit per-language HTML at the root
    summary = []
    for lang_code, entries in sorted(by_lang.items(), key=lambda kv: kv[0].lower()):
        # sort within a language: engine, voice for predictable layout
        entries.sort(key=lambda e: (engine_slug(e.get('engine','')), e.get('voice','') or ''))
        out_path = root / f"{lang_code}.html"
        make_language_html(lang_code, entries, out_path)
        found = sum(1 for e in entries if e['exists'])
        missing = len(entries) - found
        engines = {engine_slug(e.get('engine','')) for e in entries}
        print(f"[+] Wrote {out_path.name}: {len(entries)} rows, {found} ok, {missing} missing, engines={sorted(engines)}")
        summary.append((lang_code, {'file': out_path.name, 'total': len(entries), 'found': found, 'missing': missing, 'engines': engines}))

    # index.html
    make_index_html(root, summary, dupes)
    print("[+] Wrote index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
