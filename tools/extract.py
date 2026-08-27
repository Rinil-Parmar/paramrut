#!/usr/bin/env python3
"""Extract the Paramrut app's scripture corpus into structured JSON + readable Markdown."""
import json, os, re, sys, glob, shutil, collections, unicodedata

WORK = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WORK)
A    = os.path.join(WORK, 'apk/assets/flutter_assets/assets')
DATA = os.path.join(ROOT, 'data')
TEXT = os.path.join(ROOT, 'text')

def J(name):
    with open(os.path.join(A, name), encoding='utf-8') as f:
        return json.load(f)

def wr_json(rel, obj):
    p = os.path.join(DATA, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return p

def wr_text(rel, s):
    p = os.path.join(TEXT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s)
    return p

# ---------- text normalisation -------------------------------------------------
# App markup:  $ = paragraph break | ${Title} = title | ${Slok} = verse line
#              #ex1WORD /#ex1 = inline glossary term
HL_O, HL_C = '\x01', '\x02'   # sentinels for *#highlighted passage#*

def parse_footnotes(block):
    """Gloss entries trailing the main text after '@'.
    Seen as  '1. term= meaning.;'  and  '1 term= meaning.;'  runs, '$'/';'/newline separated."""
    block = block.replace('$', '\n')
    block = re.sub(r'[ \t]+', ' ', block).strip()
    NEXT = r'(?=\s*\d+\.?\s+[^=\n]{1,60}=)'
    notes = []
    for m in re.finditer(r'(\d+)\.?\s+([^=\n]{1,60}?)\s*=\s*(.*?)' + NEXT + r'|'
                         r'(\d+)\.?\s+([^=\n]{1,60}?)\s*=\s*(.*)', block, flags=re.S):
        n, term, mean = (m.group(1), m.group(2), m.group(3)) if m.group(1) else \
                        (m.group(4), m.group(5), m.group(6))
        mean = re.sub(r'\s+', ' ', mean or '').strip().strip(';').strip()
        notes.append({'n': int(n), 'term': (term or '').strip(), 'meaning': mean})
    if not notes:
        rest = re.sub(r'\s+', ' ', block).strip().strip(';').strip()
        if rest: notes.append({'n': None, 'term': None, 'meaning': rest})
    return notes

def clean(raw):
    """Return (title, [(kind, text)], footnotes). kind is 'p' (prose) or 'v' (verse)."""
    if raw is None: return None, [], []
    t = raw.replace('\r\n', '\n').replace('\xa0', ' ')
    t = re.sub(r'#ex\d*(.*?)\s*/#ex\d*', r'\1', t, flags=re.S)   # inline glossary terms
    t = re.sub(r'#/?ex\d*', '', t)                               # stragglers
    t = t.replace('*#', HL_O).replace('#*', HL_C)                # highlighted passages

    footnotes = []
    if '@' in t:
        head, _, tail = t.partition('@')
        t, footnotes = head, parse_footnotes(tail)

    title = None
    m = re.match(r'\s*\$\{Title\}(.*?)\$', t, flags=re.S)
    if m:
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        t = t[m.end():]
    t = re.sub(r'\$\{Title\}', '', t)

    out, VERSE = [], '\x00V\x00'
    t = t.replace('${Slok}', VERSE)
    for chunk in t.split('$'):
        if VERSE in chunk:
            for ln in chunk.split(VERSE):
                ln = re.sub(r'[ \t]+', ' ', ln).strip()
                if ln: out.append(('v', ln))
        else:
            c = re.sub(r'[ \t]+', ' ', chunk).strip()
            c = re.sub(r'\n{2,}', '\n', c).strip()
            if c: out.append(('p', c))
    return title, out, footnotes

def highlights(paras):
    joined = '\n'.join(x for _, x in paras)
    return [re.sub(r'\s+', ' ', h).strip()
            for h in re.findall(HL_O + r'(.*?)' + HL_C, joined, flags=re.S)]

def as_plain(paras):
    return '\n\n'.join(x for _, x in paras).replace(HL_O, '').replace(HL_C, '')

def as_md(paras):
    paras = [(k, v.replace(HL_O, '**').replace(HL_C, '**')) for k, v in paras]
    lines, i = [], 0
    while i < len(paras):
        kind, txt = paras[i]
        if kind == 'v':
            block = []
            while i < len(paras) and paras[i][0] == 'v':
                block.append(paras[i][1]); i += 1
            lines.append('\n'.join('> ' + b for b in block))
        else:
            lines.append(txt); i += 1
    return '\n\n'.join(lines)

def fn_md(notes):
    if not notes: return []
    out = ['**Notes**', '']
    for f in notes:
        if f['term']: out.append(f"{f['n']}. **{f['term']}** \u2014 {f['meaning']}")
        else: out.append(f"- {f['meaning']}")
    return out + ['']

def read_txt(path):
    if not os.path.exists(path): return None
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()

def slug(s, maxlen=60):
    s = unicodedata.normalize('NFKD', str(s))
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return (s[:maxlen].strip('-')) or 'untitled'

GU_DIGITS = str.maketrans('૦૧૨૩૪૫૬૭૮૯', '0123456789')
def gu_int(s):
    m = re.search(r'[\d૦-૯]+', str(s))
    return int(m.group().translate(GU_DIGITS)) if m else 0

stats = collections.OrderedDict()

# ============================== 1. SWAMINI VATO ================================
def swamini_vato():
    chapters = {int(c['ChId']): c for c in J('chapter.json')}
    guj = J('chapterall.json')
    hin = {(int(e['ChId']), int(e['VatNo'])): e for e in J('hindichapterall.json')}
    eng = {(int(e['chId']), int(e['VatNo'])): e for e in J('engchapter1.json')}

    records, miss_g = [], 0
    for e in guj:
        ch, no, vid = int(e['ChId']), int(e['VatNo']), int(e['VatId'])
        stem = e['VatFile'].replace('.html', '')
        rec = {'vat_id': vid, 'prakaran': ch,
               'prakaran_name_gu': (chapters.get(ch) or {}).get('ChNameGuj'),
               'vat_no': no,
               'title_gu': e.get('VatNameGuj'), 'title_translit': e.get('VatName'),
               'ref': e.get('RefFile') or None, 'text': {}}
        g = read_txt(f'{A}/textguj/chapter{ch}/{stem}.txt')
        if g is None: miss_g += 1
        else:
            _, p, fn = clean(g)
            rec['text']['gu'] = as_plain(p); rec['_gu'] = p
            if fn: rec.setdefault('footnotes', {})['gu'] = fn
            hl = highlights(p)
            if hl: rec.setdefault('highlights', {})['gu'] = hl
        h = hin.get((ch, no))
        if h:
            r = read_txt(f"{A}/text/chapter{ch}/{h['VatFile']}")
            if r:
                _, p, fn = clean(r)
                rec['text']['hi'] = as_plain(p); rec['_hi'] = p
                if fn: rec.setdefault('footnotes', {})['hi'] = fn
                rec['title_hi'] = h.get('VatNameHindi')
        en = eng.get((ch, no))
        if en:
            r = read_txt(f"{A}/textenglish/chapter{ch}/{en['VatFile']}")
            if r:
                _, p, fn = clean(r)
                rec['text']['en'] = as_plain(p); rec['_en'] = p
                if fn: rec.setdefault('footnotes', {})['en'] = fn
                rec['title_en'] = en.get('VatNameEng')
        records.append(rec)

    # topics
    topics = []
    for t in J('vishayvar.json'):
        ids = [int(x) for x in re.findall(r'\d+', t.get('VatId') or '')]
        topics.append({'id': int(t['Id']), 'name_gu': t.get('NameGuj', '').strip(),
                       'name_translit': t.get('Name'), 'vat_ids': ids})
    wr_json('topics.json', topics)

    export = [{k: v for k, v in r.items() if not k.startswith('_')} for r in records]
    wr_json('swamini-vato.json', export)

    # markdown, one file per prakaran per language
    langs = {'gu': ('gujarati', '_gu', 'title_gu'), 'hi': ('hindi', '_hi', 'title_hi'),
             'en': ('english', '_en', 'title_en')}
    counts = collections.Counter()
    for lang, (dirname, key, tkey) in langs.items():
        by_ch = collections.defaultdict(list)
        for r in records:
            if key in r: by_ch[r['prakaran']].append(r)
        for ch in sorted(by_ch):
            rows = sorted(by_ch[ch], key=lambda r: r['vat_no'])
            head = chapters.get(ch, {})
            out = [f"# Swamini Vato — Prakaran {ch}", '']
            if head.get('ChNameGuj'): out += [f"**{head['ChNameGuj'].strip()}**", '']
            out += [f"_{len(rows)} vato · language: {dirname}_", '', '---', '']
            for r in rows:
                title = (r.get(tkey) or '').strip()
                out.append(f"## {r['vat_no']}. {title}".rstrip('. ') if title else f"## {r['vat_no']}")
                out += ['', as_md(r[key]), '']
                out += fn_md((r.get('footnotes') or {}).get(lang))
                if r.get('ref'): out += [f"_Ref: {r['ref']}_", '']
                out += ['---', '']
                counts[lang] += 1
            wr_text(f'swamini-vato/{dirname}/prakaran-{ch:02d}.md', '\n'.join(out))
    stats['swamini_vato'] = {'vato': len(records), 'gujarati': counts['gu'],
                             'hindi': counts['hi'], 'english': counts['en'],
                             'prakarans': len(chapters), 'topics': len(topics),
                             'missing_gujarati_text': miss_g}
    return records

# ============================== 2. VACHANAMRUT =================================
SECTIONS = [('GP', 'Gadhada Pratham'), ('S', 'Sarangpur'), ('K', 'Kariyani'), ('L', 'Loya'),
            ('P', 'Panchala'), ('GM', 'Gadhada Madhya'), ('V', 'Vartal'), ('A', 'Amadavad'),
            ('GA', 'Gadhada Antya'), ('J', 'Jetalpur'), ('KB', 'Kariyani (misc)'),
            ('ASH', 'Ashirvad')]
SEC_NAME = dict(SECTIONS); SEC_ORDER = {k: i for i, (k, _) in enumerate(SECTIONS)}

def vachanamrut():
    idx = J('vachanall.json')
    seen, records = set(), []
    for e in idx:
        stem = e['File'].replace('.html', '')
        seen.add(stem)
        pre = re.match(r'[A-Za-z]+', stem).group().upper()
        raw = read_txt(f'{A}/textvachan/{stem}.txt')
        if raw is None: continue
        title, paras, fn = clean(raw)
        records.append({'footnotes': fn, 'highlights': highlights(paras), 'id': int(e['Id']), 'file': stem, 'section_code': pre,
                        'section': SEC_NAME.get(pre, pre), 'number': e.get('VachanNo'),
                        'name_translit': (e.get('VachanName') or '').strip(),
                        'name_gu': (e.get('NameGuj') or '').strip(),
                        'title_gu': title, 'tithi': e.get('Tithi'),
                        'date': e.get('Panchang'), 'weekday': e.get('Day'),
                        'text': as_plain(paras), '_p': paras})
    # any txt not referenced by the index
    for p in sorted(glob.glob(f'{A}/textvachan/*.txt')):
        stem = os.path.basename(p)[:-4]
        if stem in seen: continue
        pre = re.match(r'[A-Za-z]+', stem).group().upper()
        title, paras, fn = clean(read_txt(p))
        records.append({'footnotes': fn, 'highlights': highlights(paras), 'id': None, 'file': stem, 'section_code': pre,
                        'section': SEC_NAME.get(pre, pre), 'number': None,
                        'name_translit': None, 'name_gu': None, 'title_gu': title,
                        'tithi': None, 'date': None, 'weekday': None,
                        'text': as_plain(paras), '_p': paras})
    records.sort(key=lambda r: (SEC_ORDER.get(r['section_code'], 99), gu_int(r['number'] or 0), r['file']))
    wr_json('vachanamrut.json', [{k: v for k, v in r.items() if k != '_p'} for r in records])

    by_sec = collections.defaultdict(list)
    for r in records: by_sec[r['section_code']].append(r)
    for i, (code, name) in enumerate(SECTIONS, 1):
        rows = by_sec.get(code)
        if not rows: continue
        out = [f"# Vachanamrut — {name}", '', f"_{len(rows)} vachanamrut_", '', '---', '']
        for r in rows:
            h = r['title_gu'] or r['name_gu'] or r['name_translit'] or r['file']
            out += [f"## {h}", '']
            meta = [x for x in [r['name_translit'], r['tithi'], r['date'], r['weekday']] if x]
            if meta: out += ['_' + ' · '.join(str(m).strip() for m in meta) + '_', '']
            out += [as_md(r['_p']), '']
            out += fn_md(r['footnotes'])
            out += ['---', '']
        wr_text(f'vachanamrut/gujarati/{i:02d}-{slug(name)}.md', '\n'.join(out))
    stats['vachanamrut'] = {'vachanamrut': len(records),
                            'sections': {SEC_NAME.get(k, k): len(v) for k, v in
                                         sorted(by_sec.items(), key=lambda kv: SEC_ORDER.get(kv[0], 99))}}
    return records

# ========================= 3. ANIRDESHI AMRUT (discourses) =====================
def norm_kalash(v):
    v = (v or '').strip()
    m = re.search(r'[\d\u0AE6-\u0AEF]+', v)
    return f"\u0a95\u0ab3\u0ab6 - {m.group()}" if m else v

def anirdeshi_amrut():
    rows = J('aa_achaman_all.json')
    meta = {}
    for e in J('amrut.json'):
        meta[e['vinfo'].replace('.html', '')] = e
    records = []
    for e in rows:
        stem = e['filename'].replace('.txt', '')
        raw = read_txt(f"{A}/textamrut/aa_achaman_all/{e['filename']}")
        _, paras, fn = clean(raw if raw is not None else (e.get('content') or ''))
        tags = e.get('tags')
        if isinstance(tags, str):
            tags = [t.strip() for t in re.findall(r"'([^']*)'", tags)] or \
                   ([tags.strip()] if tags.strip() not in ('', '[]', 'nan') else [])
        records.append({'footnotes': fn, 'id': int(e['id']) if str(e.get('id')).isdigit() else e.get('id'),
                        'file': stem, 'date': e.get('date') or None,
                        'kalash': norm_kalash(e.get('amrut')),
                        'achaman': (e.get('achaman') or '').strip(),
                        'title': (e.get('title') or '').strip(),
                        'tags': tags or [], 'text': as_plain(paras), '_p': paras})
    records.sort(key=lambda r: (gu_int(r['kalash']), gu_int(r['achaman']), r['date'] or '', r['file']))
    wr_json('anirdeshi-amrut.json', [{k: v for k, v in r.items() if k != '_p'} for r in records])

    by = collections.defaultdict(list)
    for r in records: by[(r['kalash'], r['achaman'])].append(r)
    for (kal, ach), rows2 in sorted(by.items(), key=lambda kv: (gu_int(kv[0][0]), gu_int(kv[0][1]))):
        k, a = gu_int(kal) or 0, gu_int(ach) or 0
        yr = re.search(r'\(([\d\u0AE6-\u0AEF]{4})\)', ach)
        yr = yr.group(1).translate(GU_DIGITS) if yr else None
        fname = f'anirdeshi-amrut/kalash-{k}/achaman-{a}' + (f'-{yr}' if yr else '') + '.md'
        out = [f"# Anirdeshi Amrut — {kal}, {ach}", '', f"_{len(rows2)} sabha_", '', '---', '']
        for r in rows2:
            out += [f"## {r['date'] or r['file']}", '']
            if r['tags']: out += ['_' + ' · '.join(r['tags']) + '_', '']
            out += [as_md(r['_p']), '']
            out += fn_md(r['footnotes'])
            out += ['---', '']
        wr_text(fname, '\n'.join(out))
    stats['anirdeshi_amrut'] = {'sabha': len(records),
                                'kalash': sorted({r['kalash'] for r in records}, key=gu_int),
                                'achaman_groups': len(by)}
    return records

# ============================== 4. SHIKSHAPATRI ================================
def shikshapatri():
    base = {e['number']: e for e in J('shikshapatri.json')}
    hi   = {e['number']: e for e in J('shikshapatrihindi.json')}
    sel  = {e['number']: e for e in J('shikshapatriselected.json')}
    def strip_html(s):
        if not s: return None
        return re.sub(r'\s+\n', '\n', re.sub(r'<br\s*/?>', '\n', s)).strip()
    recs = []
    for n in sorted(set(base) | set(hi) | set(sel)):
        b, h, s = base.get(n, {}), hi.get(n, {}), sel.get(n, {})
        recs.append({'number': n,
                     'sanskrit': strip_html(b.get('sanskrit') or s.get('sanskrit') or h.get('sanskrit')),
                     'gujarati': strip_html(b.get('gujarati') or s.get('gujarati')),
                     'hindi': strip_html(h.get('hindi') or s.get('hindi') or h.get('gujarati')),
                     'selected': n in sel})
    wr_json('shikshapatri.json', recs)
    out = ['# Shikshapatri', '', f'_{len(recs)} shlokas — Sanskrit with Gujarati and Hindi_', '', '---', '']
    for r in recs:
        out += [f"## {r['number']}" + ('  ⭐' if r['selected'] else ''), '']
        if r['sanskrit']: out += ['\n'.join('> ' + l for l in r['sanskrit'].split('\n') if l.strip()), '']
        if r['gujarati']: out += ['**ગુજરાતી** — ' + r['gujarati'].replace('\n', ' '), '']
        if r['hindi']:    out += ['**हिन्दी** — ' + r['hindi'].replace('\n', ' '), '']
        out += ['---', '']
    wr_text('shikshapatri.md', '\n'.join(out))
    stats['shikshapatri'] = {'shlokas': len(recs), 'selected': sum(r['selected'] for r in recs)}

# ============================ 5. QUOTES / PARISISHTH ===========================
GURU_HARIPRASAD  = '\u0a97\u0ac1\u0ab0\u0ac1\u0ab9\u0ab0\u0abf \u0ab9\u0ab0\u0abf\u0aaa\u0acd\u0ab0\u0ab8\u0abe\u0aa6 \u0ab8\u0acd\u0ab5\u0abe\u0aae\u0ac0\u0ab6\u0acd\u0ab0\u0ac0'
GURU_PRABODHJIVAN = '\u0a97\u0ac1\u0ab0\u0ac1\u0ab9\u0ab0\u0abf \u0aaa\u0acd\u0ab0\u0aac\u0acb\u0aa7\u0a9c\u0ac0\u0ab5\u0aa8 \u0ab8\u0acd\u0ab5\u0abe\u0aae\u0ac0\u0a9c\u0ac0'

def norm_guru(raw, quote):
    '''Collapse 30+ spelling variants to two canonical gurus; recover blanks
    from the attribution line that trails the quote text.'''
    for hay in (raw or '', quote or ''):
        if re.search(r'\u0ab9\u0ab0\u0abf\u0aaa\u0acd\u0ab0\u0ab8\u0abe\u0aa6|Hariprasad', hay):
            return GURU_HARIPRASAD
        if re.search(r'\u0aaa\u0acd\u0ab0\u0aac\u0acb\u0aa7|Prabodh|\u092a\u094d\u0930\u092c\u094b\u0927', hay):
            return GURU_PRABODHJIVAN
    return None

def quotes():
    recs = []
    for q in J('quotes.json'):
        qt = (q.get('quote') or '').strip()
        raw = (q.get('guru') or '').strip()
        recs.append({'number': q['number'], 'quote': qt,
                     'guru': norm_guru(raw, qt), 'guru_raw': raw or None,
                     'date_gu': q.get('date'),
                     'place': (q.get('place') or '').strip() or None})
    wr_json('quotes.json', recs)
    out = ['# Guruhari Paravani — Quotes', '', f'_{len(recs)} quotes_', '', '---', '']
    for r in recs:
        out += [f"**{r['number']}.** {r['quote']}", '',
                '_' + ' · '.join(x for x in [r['guru'], r['place'], r['date_gu']] if x) + '_', '']
    wr_text('quotes.md', '\n'.join(out))
    stats['quotes'] = {'quotes': len(recs),
                       'gurus': dict(collections.Counter(r['guru'] or 'unattributed' for r in recs))}

def html_body(raw):
    """Pull the reading pane out of an app HTML page, dropping its reader-tool chrome."""
    if not raw: return None
    m = re.search(r'<div[^>]*class="vaat_ind"[^>]*>(.*)', raw, flags=re.S)
    body = m.group(1) if m else raw
    body = re.sub(r'(?is)</body>.*', '', body)
    body = re.sub(r'(?is)<(script|style|head|ul)[^>]*>.*?</\1>', ' ', body)
    body = re.sub(r'(?is)<h1[^>]*>.*?</h1>', ' ', body)      # duplicates our heading
    body = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</li>', '\n', body)
    body = re.sub(r'<[^>]+>', ' ', body)
    body = (body.replace('&nbsp;', ' ').replace('&amp;', '&')
                .replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"'))
    body = re.sub(r'[ \t]+', ' ', body)
    lines = [l.strip() for l in body.split('\n')]
    return '\n'.join(l for l in lines if l) or None

def parisishth():
    recs = []
    for e in J('parisishth.json'):
        body = None
        for d in ('html/parisist', 'html/parisist1'):
            p = f"{A}/{d}/{e['FileName']}"
            if os.path.exists(p):
                body = html_body(read_txt(p)); break
        recs.append({'id': int(e['Id']), 'title_gu': e.get('TitleGuj', '').strip(),
                     'title_translit': e.get('TitleEng'), 'file': e['FileName'], 'text': body})
    wr_json('parisishth.json', recs)
    out = ['# Parisishth \u2014 Glossary & Biographies', '', f'_{len(recs)} entries_', '', '---', '']
    for r in recs:
        out += [f"## {r['title_gu'] or r['title_translit']}", '']
        if r['title_translit']: out += [f"_{r['title_translit']}_", '']
        if r['text']: out += [r['text'], '']
        out += ['---', '']
    wr_text('parisishth.md', '\n'.join(out))
    stats['parisishth'] = {'entries': len(recs),
                           'with_text': sum(1 for r in recs if r['text'])}

def ashirvad():
    raw = read_txt(f'{A}/textvachan/ASH-1.txt')
    if not raw: return
    title, paras, _fn = clean(raw)
    wr_text('ashirvad.md', f"# {title or 'Ashirvad'}\n\n{as_md(paras)}\n")
    stats['ashirvad'] = {'documents': 1}

# ================================= 6. SOURCE ===================================
def source(force=False):
    dst = os.path.join(ROOT, '_source')
    if os.path.isdir(dst) and os.listdir(dst) and not force:
        return                       # already mirrored; pass --source to refresh
    os.makedirs(dst, exist_ok=True)
    for sub in ['html', 'html1', 'amrut', 'bhajan', 'text', 'textguj', 'textenglish',
                'textvachan', 'textamrut', 'images']:
        s = os.path.join(A, sub)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(dst, sub), dirs_exist_ok=True)
    os.makedirs(os.path.join(dst, 'json'), exist_ok=True)
    for p in glob.glob(f'{A}/*.json'):
        shutil.copy2(p, os.path.join(dst, 'json', os.path.basename(p)))
    for p in glob.glob(f'{A}/*.sqlite'):
        shutil.copy2(p, os.path.join(dst, os.path.basename(p)))

if __name__ == '__main__':
    os.makedirs(DATA, exist_ok=True); os.makedirs(TEXT, exist_ok=True)
    swamini_vato(); vachanamrut(); anirdeshi_amrut()
    shikshapatri(); quotes(); parisishth(); ashirvad()
    source(force='--source' in sys.argv)
    wr_json('index.json', {'source': {'app': 'Paramrut', 'package': 'org.hariprabodham.swaminivato',
                                      'version': '5.1', 'publisher': 'HariPrabodham'},
                           'collections': stats})
    print(json.dumps(stats, ensure_ascii=False, indent=2))
