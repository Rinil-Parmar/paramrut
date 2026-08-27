#!/usr/bin/env python3
"""Add navigation to the generated corpus: a table of contents inside every
content file, and an index page at every directory level.

Runs after extract.py. Touches only navigation — never the scripture text."""
import json, os, re, glob, collections, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, 'text')
DATA = os.path.join(ROOT, 'data')
MARK = '<!-- nav:generated -->'

IDX = json.load(open(os.path.join(DATA, 'index.json'), encoding='utf-8'))['collections']

def gh_anchor(text, seen):
    """Reproduce GitHub's heading-anchor slug, including its -1/-2 dedupe.

    GitHub strips punctuation and symbols but keeps letters, numbers AND combining
    marks. Python's word-class drops Mn/Mc, which would mangle every Gujarati matra, so the
    categories are tested directly."""
    out = []
    for ch in text.strip().lower():
        if ch == ' ':
            out.append('-')
        elif ch in '-_' or unicodedata.category(ch)[0] in ('L', 'N', 'M'):
            out.append(ch)
    a = ''.join(out)
    n = seen[a]; seen[a] += 1
    return a if n == 0 else f'{a}-{n}'

def rel(frm, to):
    return os.path.relpath(to, os.path.dirname(frm)).replace(os.sep, '/')

def _label(readme, fallback):
    """Prefer the target index page's own H1 as the crumb label."""
    try:
        for ln in open(readme, encoding='utf-8'):
            if ln.startswith('# '):
                return ln[2:].strip().split('—')[0].strip()
    except OSError:
        pass
    return fallback.replace('-', ' ').title()

def crumbs(path):
    """Root-first trail, skipping directories that have no index page."""
    parts, chain = [f'[← Paramrut]({rel(path, os.path.join(ROOT, "README.md"))})'], []
    d = os.path.dirname(os.path.abspath(path))
    while os.path.normpath(d) != os.path.normpath(ROOT):
        chain.append(d)
        d = os.path.dirname(d)
    for d in reversed(chain):                       # outermost → innermost
        idxf = os.path.join(d, 'README.md')
        if not os.path.exists(idxf): continue       # no index here, skip the level
        if os.path.normpath(idxf) == os.path.normpath(os.path.abspath(path)): continue
        parts.append(f'[{_label(idxf, os.path.basename(d))}]({rel(path, idxf)})')
    return ' · '.join(parts)

def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(body)

# ---------------------------------------------------------------- TOC injection
def inject_toc(path):
    with open(path, encoding='utf-8') as f: src = f.read()
    if MARK in src: return 0                       # already navigated
    lines = src.split('\n')

    seen, entries = collections.defaultdict(int), []
    for ln in lines:
        if ln.startswith('## '):
            title = ln[3:].strip()
            entries.append((title, gh_anchor(title, seen)))
    if not entries: return 0

    try:    cut = next(i for i, l in enumerate(lines) if l.strip() == '---')
    except StopIteration: return 0

    items = [f'- [{t}](#{a})' for t, a in entries]
    open_by_default = len(entries) <= 25
    toc = [MARK, '',
           f'<details{" open" if open_by_default else ""}>',
           f'<summary><b>Contents</b> — {len(entries)} entries</summary>', '',
           *items, '', '</details>', '']

    head = [crumbs(path), ''] + lines[:cut]
    write(path, '\n'.join(head + toc + lines[cut:]))
    return len(entries)

# ------------------------------------------------------------------- index pages
def swamini_vato_index():
    sv = IDX['swamini_vato']
    chapters = {}
    for p in sorted(glob.glob(f'{TEXT}/swamini-vato/*/prakaran-*.md')):
        lang = os.path.basename(os.path.dirname(p))
        n = int(re.search(r'prakaran-(\d+)', p).group(1))
        first = open(p, encoding='utf-8').read().split('\n')
        name = next((l.strip('* ') for l in first if l.startswith('**')), '')
        cnt = next((re.search(r'_(\d[\d,]*) vato', l) for l in first if ' vato' in l), None)
        chapters.setdefault(n, {'name': name, 'langs': {}})
        chapters[n]['langs'][lang] = (p, int(cnt.group(1).replace(',', '')) if cnt else 0)

    rows = []
    for n in sorted(chapters):
        c = chapters[n]; L = c['langs']
        def cell(lang):
            if lang not in L: return '—'
            p, k = L[lang]
            return f'[{k:,}]({rel(f"{TEXT}/swamini-vato/README.md", p)})'
        rows.append(f'| {n} | {c["name"]} | {cell("gujarati")} | {cell("hindi")} | {cell("english")} |')

    body = f"""{crumbs(f'{TEXT}/swamini-vato/README.md')}

# Swamini Vato

The talks of Aksharbrahma Gunatitanand Swami — **{sv['vato']:,} vato** across
**{sv['prakarans']} prakarans**. Gujarati is complete; Hindi and English are partial
translations in the source app.

Numbers in the table are vato counts and link straight to that prakaran.

| # | Prakaran | ગુજરાતી | हिन्दी | English |
|---:|---|---:|---:|---:|
{chr(10).join(rows)}
| | **Total** | **{sv['gujarati']:,}** | **{sv['hindi']:,}** | **{sv['english']:,}** |

Each vato carries its cross-reference to the Vachanamrut where the source marks one,
and its footnote glosses are rendered as a **Notes** list beneath the text.

### Thematic index

[`data/topics.json`]({rel(f'{TEXT}/swamini-vato/README.md', f'{DATA}/topics.json')}) maps
**{sv['topics']} themes** (vishayvar) onto vato ids — useful for reading by subject rather
than in order.

### Also as data

[`data/swamini-vato.json`]({rel(f'{TEXT}/swamini-vato/README.md', f'{DATA}/swamini-vato.json')})
— every vato with all three languages, footnotes and references on one record.
"""
    write(f'{TEXT}/swamini-vato/README.md', body)

def vachanamrut_index():
    va = IDX['vachanamrut']
    rows = []
    for p in sorted(glob.glob(f'{TEXT}/vachanamrut/gujarati/*.md')):
        head = open(p, encoding='utf-8').read().split('\n')
        title = next(l[2:].strip() for l in head if l.startswith('# '))
        name = title.split('—')[-1].strip()
        m = next((re.search(r'_(\d+) vachanamrut', l) for l in head if 'vachanamrut_' in l), None)
        rows.append(f'| [{name}]({rel(f"{TEXT}/vachanamrut/README.md", p)}) | {m.group(1) if m else ""} |')

    body = f"""{crumbs(f'{TEXT}/vachanamrut/README.md')}

# Vachanamrut

The discourses of Bhagwan Swaminarayan — **{va['vachanamrut']} vachanamrut**, in Gujarati,
organised by the place each was spoken.

| Section | Count |
|---|---:|
{chr(10).join(rows)}

Each entry keeps its tithi, Gregorian date and weekday. Passages the source marks as key
teachings are rendered in **bold** and are also collected per-record in the JSON.

### Also as data

[`data/vachanamrut.json`]({rel(f'{TEXT}/vachanamrut/README.md', f'{DATA}/vachanamrut.json')})
— one record per vachanamrut with `section`, `tithi`, `date`, `text` and `highlights`.
"""
    write(f'{TEXT}/vachanamrut/README.md', body)

def anirdeshi_index():
    aa = IDX['anirdeshi_amrut']
    by_k = collections.defaultdict(list)
    for p in sorted(glob.glob(f'{TEXT}/anirdeshi-amrut/kalash-*/achaman-*.md')):
        k = int(re.search(r'kalash-(\d+)', p).group(1))
        head = open(p, encoding='utf-8').read().split('\n')
        title = next(l[2:].strip() for l in head if l.startswith('# '))
        m = next((re.search(r'_(\d+) sabha', l) for l in head if 'sabha_' in l), None)
        label = title.split('—')[-1].strip()
        by_k[k].append((label, p, m.group(1) if m else ''))

    secs = []
    for k in sorted(by_k):
        rows = '\n'.join(f'| [{lbl}]({rel(f"{TEXT}/anirdeshi-amrut/README.md", p)}) | {n} |'
                         for lbl, p, n in by_k[k])
        secs.append(f'### Kalash {k}\n\n| Achaman | Sabha |\n|---|---:|\n{rows}\n')

    body = f"""{crumbs(f'{TEXT}/anirdeshi-amrut/README.md')}

# Anirdeshi Amrut

Divine discourses of Guruhari Hariprasad Swamishri — **{aa['sabha']:,} sabha** gathered into
**3 kalash** and **{aa['achaman_groups']} achaman**, each dated.

{chr(10).join(secs)}
Every sabha carries the subject tags the source assigns it.

### Also as data

[`data/anirdeshi-amrut.json`]({rel(f'{TEXT}/anirdeshi-amrut/README.md', f'{DATA}/anirdeshi-amrut.json')})
— one record per sabha with `date`, `kalash`, `achaman`, `tags` and `text`, sorted chronologically.
"""
    write(f'{TEXT}/anirdeshi-amrut/README.md', body)

def text_index():
    sv, va, aa = IDX['swamini_vato'], IDX['vachanamrut'], IDX['anirdeshi_amrut']
    R = f'{TEXT}/README.md'
    body = f"""{crumbs(R)}

# Reading the corpus

Everything here is Markdown, so it renders directly on GitHub — click through and read.
Every file opens with its own table of contents.

## Collections

| | Collection | Size | Language |
|---|---|---|---|
| 📖 | **[Swamini Vato](swamini-vato/README.md)** | {sv['vato']:,} vato · {sv['prakarans']} prakarans | ગુજરાતી · हिन्दी · English |
| 🪔 | **[Vachanamrut](vachanamrut/README.md)** | {va['vachanamrut']} vachanamrut · 12 sections | ગુજરાતી |
| 🌸 | **[Anirdeshi Amrut](anirdeshi-amrut/README.md)** | {aa['sabha']:,} sabha · 3 kalash | ગુજરાતી |
| 📜 | **[Shikshapatri](shikshapatri.md)** | {IDX['shikshapatri']['shlokas']} shlokas | संस्कृत · ગુજરાતી · हिन्दी |
| 💬 | **[Guruhari Paravani](quotes.md)** | {IDX['quotes']['quotes']} quotes | ગુજરાતી |
| 📇 | **[Parisishth](parisishth.md)** | {IDX['parisishth']['entries']} entries | ગુજરાતી |
| 🙏 | **[Ashirvad](ashirvad.md)** | 1 | ગુજરાતી |

## How the pages are laid out

Long collections are split so no single file is unwieldy — Swamini Vato by prakaran,
Vachanamrut by place, Anirdeshi Amrut by achaman. Each has an index page of its own,
linked above.

Inside a page:

- **Headings** are the individual vato / vachanamrut / sabha, so the sidebar outline works.
- **Notes** beneath a passage are the source's own numbered glosses.
- **Bold passages** in the Vachanamrut are the ones the source marks as key teachings.
- **Blockquotes** are verse — shlokas and citations.
"""
    write(R, body)

def data_index():
    R = f'{DATA}/README.md'
    sizes = {os.path.basename(p): os.path.getsize(p) for p in glob.glob(f'{DATA}/*.json')}
    def mb(n): return f'{n/1048576:.1f} MB' if n >= 1048576 else f'{n/1024:.0f} KB'
    rows = [
        ('swamini-vato.json', f"{IDX['swamini_vato']['vato']:,}", '`vat_id`, `prakaran`, `vat_no`, `title_gu/hi/en`, `text.{gu,hi,en}`, `footnotes`, `ref`'),
        ('vachanamrut.json', f"{IDX['vachanamrut']['vachanamrut']}", '`id`, `section`, `number`, `name_gu`, `title_gu`, `tithi`, `date`, `weekday`, `text`, `highlights`'),
        ('anirdeshi-amrut.json', f"{IDX['anirdeshi_amrut']['sabha']:,}", '`id`, `date`, `kalash`, `achaman`, `title`, `tags`, `text`'),
        ('shikshapatri.json', f"{IDX['shikshapatri']['shlokas']}", '`number`, `sanskrit`, `gujarati`, `hindi`, `selected`'),
        ('quotes.json', f"{IDX['quotes']['quotes']}", '`number`, `quote`, `guru`, `guru_raw`, `date_gu`, `place`'),
        ('parisishth.json', f"{IDX['parisishth']['entries']}", '`id`, `title_gu`, `title_translit`, `text`'),
        ('topics.json', f"{IDX['swamini_vato']['topics']}", '`id`, `name_gu`, `name_translit`, `vat_ids`'),
        ('index.json', '—', 'provenance and record counts for every collection'),
    ]
    table = '\n'.join(f'| [`{f}`]({f}) | {n} | {mb(sizes.get(f,0))} | {s} |' for f, n, s in rows)
    body = f"""{crumbs(R)}

# Data

The same corpus as [`text/`](../text/README.md), as UTF-8 JSON — one file per collection,
each a flat array of records.

| File | Records | Size | Fields |
|---|---:|---:|---|
{table}

## Notes on the fields

- **`text`** is plain text with paragraphs separated by blank lines. On Swamini Vato it is an
  object keyed by language (`gu`, `hi`, `en`) holding only the languages that exist for that vato.
- **`footnotes`** are the source's numbered glosses, parsed into `{{n, term, meaning}}`.
- **`highlights`** (Vachanamrut) are the passages the source marks as key teachings.
- **`ref`** on a vato points at the Vachanamrut the source cross-references.
- **`topics.json`** joins to `swamini-vato.json` on `vat_id`.

## Example

```python
import json

vato = json.load(open('data/swamini-vato.json', encoding='utf-8'))

# every vato that has an English translation
english = [v for v in vato if 'en' in v['text']]

# read a theme
topics = json.load(open('data/topics.json', encoding='utf-8'))
mahima = next(t for t in topics if 'Mahima' in (t['name_translit'] or ''))
by_id  = {{v['vat_id']: v for v in vato}}
for i in mahima['vat_ids']:
    print(by_id[i]['text']['gu'])
```
"""
    write(R, body)

if __name__ == '__main__':
    # index pages first: crumbs link to them and read their headings for labels
    text_index(); data_index()
    swamini_vato_index(); vachanamrut_index(); anirdeshi_index()
    n = files = 0
    for p in glob.glob(f'{TEXT}/**/*.md', recursive=True):
        if os.path.basename(p) == 'README.md': continue
        k = inject_toc(p)
        if k: files += 1; n += k
    print(f'nav: {n:,} TOC entries across {files} files; 5 index pages')
