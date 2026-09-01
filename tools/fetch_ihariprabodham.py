#!/usr/bin/env python3
"""Fetch the textual corpus published by ihariprabodham.org and render it to Markdown.

The website (a React app) reads its content from public, unauthenticated data files
and APIs. Unlike the app work, the full text ships as JSON with the text inline, or
as clean structured HTML — no OCR needed. This tool captures every *textual* source
(text, descriptions and links); it does not download images, audio or video, only
records their links.

Sources (all mirrored verbatim into _source/ihariprabodham/):
    prasang-index.json      965  incident stories        (full text via /data/prasang/*.html)
    quotes.json             541  guru paravani quotes
    vato-index.json        1511  Swamini Vato prakaran 1-7   (app markup)
    vato2-index.json       2314  Swamini Vato prakaran 8-16  (app markup)
    vachan-index.json       274  Vachanamrut                 (app markup)
    kirtan-index.json       514  kirtan / shlok lyrics       (via /data/*.html)
    paramrut-index.json     232  daily pravachan transcripts (via /data/paramrut/*.html)
    worker ?endpoint=…      pravachan 246 · vicharan 295 · hariprasangam 958 (metadata)
    api ?pradesh=          2263  full discourse/darshan catalogue (text + YouTube links)

The app's private markup ($ / ${Title} / ${Slok} / #ex1../  / @ / *#..#*) is decoded
exactly as in extract.py. HTML pages are reduced to their reading pane (title_gu +
vaat_ind paragraphs), dropping the reader-tool chrome. Text is otherwise unchanged.

    python3 tools/fetch_ihariprabodham.py [quotes vato vachan prasang kirtan \
                                           transcripts discourses vicharan pravachan-notes]
    python3 tools/fetch_ihariprabodham.py --refetch-html   # re-pull cached HTML pages
"""

import argparse, collections, concurrent.futures as cf, html as _html, json, re, sys
import unicodedata, urllib.request, hashlib
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "_source" / "ihariprabodham"
DATA = ROOT / "data" / "ihariprabodham"
TEXT = ROOT / "text" / "ihariprabodham"
HTMLCACHE = SRC / "html"
UA = "Mozilla/5.0"
SITE = "https://www.ihariprabodham.org"

# ── app markup decoder (verbatim from extract.py) ────────────────────────────
HL_O, HL_C = "\x01", "\x02"


def parse_footnotes(block):
    block = block.replace("$", "\n")
    block = re.sub(r"[ \t]+", " ", block).strip()
    NEXT = r"(?=\s*\d+\.?\s+[^=\n]{1,60}=)"
    notes = []
    for m in re.finditer(r"(\d+)\.?\s+([^=\n]{1,60}?)\s*=\s*(.*?)" + NEXT + r"|"
                         r"(\d+)\.?\s+([^=\n]{1,60}?)\s*=\s*(.*)", block, flags=re.S):
        n, term, mean = (m.group(1), m.group(2), m.group(3)) if m.group(1) else \
                        (m.group(4), m.group(5), m.group(6))
        mean = re.sub(r"\s+", " ", mean or "").strip().strip(";").strip()
        notes.append({"n": int(n), "term": (term or "").strip(), "meaning": mean})
    if not notes:
        rest = re.sub(r"\s+", " ", block).strip().strip(";").strip()
        if rest:
            notes.append({"n": None, "term": None, "meaning": rest})
    return notes


def clean(raw):
    """Return (title, [(kind, text)], footnotes); kind 'p' prose / 'v' verse."""
    if raw is None:
        return None, [], []
    t = raw.replace("\r\n", "\n").replace("\xa0", " ")
    t = re.sub(r"#ex\d*(.*?)\s*/#ex\d*", r"\1", t, flags=re.S)
    t = re.sub(r"#/?ex\d*", "", t)
    t = t.replace("*#", HL_O).replace("#*", HL_C)
    footnotes = []
    if "@" in t:
        head, _, tail = t.partition("@")
        t, footnotes = head, parse_footnotes(tail)
    title = None
    m = re.match(r"\s*\$\{Title\}(.*?)\$", t, flags=re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        t = t[m.end():]
    t = re.sub(r"\$\{Title\}", "", t)
    out, VERSE = [], "\x00V\x00"
    t = t.replace("${Slok}", VERSE)
    for chunk in t.split("$"):
        if VERSE in chunk:
            for ln in chunk.split(VERSE):
                ln = re.sub(r"[ \t]+", " ", ln).strip()
                if ln:
                    out.append(("v", ln))
        else:
            c = re.sub(r"[ \t]+", " ", chunk).strip()
            c = re.sub(r"\n{2,}", "\n", c).strip()
            if c:
                out.append(("p", c))
    return title, out, footnotes


def highlights(paras):
    joined = "\n".join(x for _, x in paras)
    return [re.sub(r"\s+", " ", h).strip()
            for h in re.findall(HL_O + r"(.*?)" + HL_C, joined, flags=re.S)]


def as_md(paras):
    paras = [(k, v.replace(HL_O, "**").replace(HL_C, "**")) for k, v in paras]
    lines, i = [], 0
    while i < len(paras):
        kind, txt = paras[i]
        if kind == "v":
            block = []
            while i < len(paras) and paras[i][0] == "v":
                block.append(paras[i][1]); i += 1
            lines.append("\n".join("> " + b for b in block))
        else:
            lines.append(txt); i += 1
    return "\n\n".join(lines)


def as_plain(paras):
    return "\n\n".join(x for _, x in paras).replace(HL_O, "").replace(HL_C, "")


def fn_md(notes):
    if not notes:
        return []
    out = ["", "**Notes**", ""]
    for f in notes:
        if f["term"]:
            out.append(f"{f['n']}. **{f['term']}** — {f['meaning']}")
        else:
            out.append(f"- {f['meaning']}")
    return out


# ── HTML reading-pane extractor ──────────────────────────────────────────────
def html_body(raw):
    """title_gu + vaat_ind paragraphs from an ihariprabodham reader page."""
    if not raw:
        return None, None
    tm = re.search(r'<div[^>]*class="title_gu"[^>]*>(.*?)</div>', raw, flags=re.S | re.I)
    title = None
    if tm:
        title = re.sub(r"<[^>]+>", " ", tm.group(1))
        title = re.sub(r"\s+", " ", _html.unescape(title)).strip() or None
    m = re.search(r'<div[^>]*class="vaat_ind"[^>]*>(.*)', raw, flags=re.S | re.I)
    body = m.group(1) if m else raw
    body = re.sub(r"(?is)</body>.*", "", body)
    body = re.sub(r"(?is)<(script|style|head|ul)[^>]*>.*?</\1>", " ", body)
    # paragraph boundaries
    body = re.sub(r"(?i)</p>|<br\s*/?>|</div>|</li>", "\n", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = _html.unescape(body)
    body = re.sub(r"[ \t]+", " ", body)
    paras = [re.sub(r"\s+", " ", p).strip() for p in body.split("\n")]
    paras = [p for p in paras if p]
    return title, ("\n\n".join(paras) or None)


# ── markdown page builder (paramrut style) ───────────────────────────────────
MARK = "<!-- nav:generated -->"


def gh_anchor(text, seen):
    out = []
    for ch in text.strip().lower():
        if ch == " ":
            out.append("-")
        elif ch in "-_" or unicodedata.category(ch)[0] in ("L", "N", "M"):
            out.append(ch)
    a = "".join(out); n = seen[a]; seen[a] += 1
    return a if n == 0 else f"{a}-{n}"


def build_page(crumb, title, subtitle, entries, extra_top=None):
    """entries: list of (heading, [body_line,...])."""
    seen = collections.defaultdict(int)
    toc, body = [], []
    for heading, lines in entries:
        a = gh_anchor(heading, seen)
        toc.append(f"- [{heading}](#{a})")
        body += [f"\n## {heading}\n", *lines, "\n---"]
    open_toc = len(entries) <= 25
    out = [crumb, "", f"# {title}", "", subtitle, ""]
    if extra_top:
        out += [extra_top, ""]
    out += [MARK, "",
            f'<details{" open" if open_toc else ""}>',
            f"<summary><b>Contents</b> — {len(entries)} entries</summary>", "",
            *toc, "", "</details>", "", "---", *body, ""]
    return "\n".join(out) + "\n"


def load(name):
    return json.loads((SRC / name).read_text(encoding="utf-8-sig"))


def wj(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch_html_many(kind, files, base, refetch=False):
    """Download + cache a set of reader HTML pages concurrently. Returns {file: raw}."""
    d = HTMLCACHE / kind
    d.mkdir(parents=True, exist_ok=True)
    todo = [f for f in files if refetch or not (d / f).exists()]
    if todo:
        print(f"    fetching {len(todo)} HTML pages ({kind})…")

        def one(f):
            try:
                raw = urllib.request.urlopen(
                    urllib.request.Request(f"{base}/{f}", headers={"User-Agent": UA}),
                    timeout=30).read()
                (d / f).write_bytes(raw); return f, True
            except Exception:
                return f, False
        ok = 0
        with cf.ThreadPoolExecutor(max_workers=16) as ex:
            for i, (f, good) in enumerate(ex.map(one, todo), 1):
                ok += good
                if i % 200 == 0:
                    print(f"      {i}/{len(todo)}")
        print(f"    cached {ok}/{len(todo)} new")
    out = {}
    for f in files:
        p = d / f
        if p.exists():
            out[f] = p.read_text(encoding="utf-8-sig", errors="replace")
    return out


CRUMB_ROOT = "[← iHariPrabodham](../README.md)"
CRUMB_SUB = "[← iHariPrabodham](../../README.md) · [{parent}]({plink})"


# ── source: quotes ───────────────────────────────────────────────────────────
def norm_guru(g):
    if not g:
        return None
    if "પ્રબોધ" in g:
        return "ગુરુહરિ પ્રબોધજીવન સ્વામીજી"
    if "હરિપ્રસાદ" in g:
        return "ગુરુહરિ હરિપ્રસાદ સ્વામીશ્રી"
    return g.strip()


def do_quotes():
    recs = load("quotes.json")
    out = []
    for r in recs:
        out.append({"number": r.get("number"), "quote": (r.get("quote") or "").strip(),
                    "guru": norm_guru(r.get("guru")), "guru_raw": r.get("guru"),
                    "date_gu": r.get("date"), "date_en": r.get("englishdate"),
                    "place": (r.get("place") or "").strip() or None})
    wj(DATA / "quotes.json", out)
    entries = []
    for r in out:
        head = f"{r['number']}. {r['quote'][:48]}…" if len(r["quote"]) > 50 else f"{r['number']}. {r['quote']}"
        lines = [r["quote"], ""]
        meta = " · ".join(x for x in [r["guru"], r["date_gu"], r["place"]] if x)
        if meta:
            lines.append(f"_{meta}_")
        entries.append((head, lines))
    sub = f"*Paravani of Guruhari Prabodhjivan Swamiji and Guruhari Hariprasad Swamishri.*  \n**{len(out)} quotes.**"
    (TEXT / "quotes.md").write_text(
        build_page(CRUMB_ROOT, "Guruhari Paravani", sub, entries), encoding="utf-8")
    print(f"  quotes: {len(out)}")
    return len(out)


# ── source: Swamini Vato ─────────────────────────────────────────────────────
def do_swamini_vato():
    recs = load("vato-index.json") + load("vato2-index.json")
    by_p = collections.defaultdict(list)
    data = []
    for r in recs:
        p = int(r["chId"])
        title, paras, notes = clean(r["content"])
        m = re.match(r"\s*\((\d+)\)", r["content"])
        vno = int(m.group(1)) if m else None
        rec = {"prakaran": p, "vat_no": vno, "file": r["file"],
               "text": as_plain(paras), "footnotes": notes}
        data.append(rec)
        by_p[p].append((rec, paras, notes))
    wj(DATA / "swamini-vato.json", data)
    d = TEXT / "swamini-vato"; d.mkdir(parents=True, exist_ok=True)
    idx = [CRUMB_ROOT, "", "# Swamini Vato", "",
           f"*The Swamini Vato of Gunatitanand Swami — {len(data)} vato across 16 prakaran.*", "",
           "| Prakaran | Vato |", "|---|---:|"]
    for p in sorted(by_p):
        idx.append(f"| [Prakaran {p}](prakaran-{p:02d}.md) | {len(by_p[p])} |")
        entries = []
        for rec, paras, notes in by_p[p]:
            head = f"Vato {rec['vat_no']}" if rec["vat_no"] else rec["file"]
            lines = [as_md(paras)] + fn_md(notes)
            entries.append((head, lines))
        crumb = "[← iHariPrabodham](../../README.md) · [Swamini Vato](README.md)"
        (d / f"prakaran-{p:02d}.md").write_text(
            build_page(crumb, f"Swamini Vato — Prakaran {p}",
                       f"_{len(entries)} vato_", entries), encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  swamini-vato: {len(data)} across {len(by_p)} prakaran")
    return len(data)


# ── source: Vachanamrut ──────────────────────────────────────────────────────
VSEC = [("GP", "Gadhada Pratham"), ("S", "Sarangpur"), ("K", "Kariyani"), ("L", "Loya"),
        ("P", "Panchala"), ("GM", "Gadhada Madhya"), ("V", "Vartal"), ("A", "Amdavad"),
        ("GA", "Gadhada Antya"), ("J", "Jetalpur"), ("KB", "Kariyani (misc)"), ("ASH", "Ashirvad")]
VMAP = dict(VSEC)


def do_vachanamrut():
    recs = load("vachan-index.json")
    by_s = collections.defaultdict(list)
    data = []
    for r in recs:
        m = re.match(r"([A-Za-z]+)-?(\d+)", r["file"])
        code, num = (m.group(1), int(m.group(2))) if m else ("?", 0)
        title, paras, notes = clean(r["content"])
        rec = {"section": VMAP.get(code, code), "code": code, "number": num,
               "title_gu": title, "file": r["file"], "text": as_plain(paras),
               "highlights": highlights(paras)}
        data.append(rec); by_s[code].append((rec, paras))
    wj(DATA / "vachanamrut.json", data)
    d = TEXT / "vachanamrut"; d.mkdir(parents=True, exist_ok=True)
    idx = [CRUMB_ROOT, "", "# Vachanamrut", "",
           f"*The Vachanamrut — {len(data)} discourses of Bhagwan Swaminarayan.*", "",
           "| Section | Count |", "|---|---:|"]
    for code, name in VSEC:
        if code not in by_s:
            continue
        grp = sorted(by_s[code], key=lambda t: t[0]["number"])
        slug = name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        idx.append(f"| [{name}]({slug}.md) | {len(grp)} |")
        entries = []
        for rec, paras in grp:
            head = f"{name} {rec['number']}" + (f" — {rec['title_gu']}" if rec["title_gu"] else "")
            entries.append((head, [as_md(paras)]))
        crumb = "[← iHariPrabodham](../../README.md) · [Vachanamrut](README.md)"
        (d / f"{slug}.md").write_text(
            build_page(crumb, f"Vachanamrut — {name}", f"_{len(entries)} vachanamrut_", entries),
            encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  vachanamrut: {len(data)} across {len(by_s)} sections")
    return len(data)


# ── source: Prasang (incident stories) ───────────────────────────────────────
def do_prasang(refetch=False):
    index = load("prasang-index.json")
    worker = {w["PsgContentFile"]: w for w in load("worker-hariprasangam.json")}
    cats = {int(k): v for k, v in load("prasang-categories.json").items()}
    files = [r["file"] for r in index if r["file"].startswith("psg")]
    pages = fetch_html_many("prasang", files, f"{SITE}/data/prasang", refetch)
    by_cat = collections.defaultdict(list)
    data = []
    for r in index:
        f = r["file"]
        title, body = html_body(pages.get(f, "")) if f in pages else (None, None)
        w = worker.get(f, {})
        cid = int(w.get("CatId") or 0)
        rec = {"id": w.get("PsgId"), "file": f,
               "title": title or (r.get("title") or "").replace("(newfile)", "").strip() or None,
               "title_en": w.get("EnglishTitle"), "category_id": cid,
               "category": cats.get(cid, {}).get("gu") if cid else None,
               "date": (w.get("PubDate") or {}).get("date", "").split(" ")[0] if isinstance(w.get("PubDate"), dict) else None,
               "text": body}
        data.append(rec); by_cat[cid].append(rec)
    wj(DATA / "prasang.json", data)
    d = TEXT / "prasang"; d.mkdir(parents=True, exist_ok=True)
    idx = [CRUMB_ROOT, "", "# Prasang", "",
           f"*Prasang — {len(data)} incident-stories from the lives of the gurus, by theme.*", "",
           "| Theme | Prasang |", "|---|---:|"]
    order = sorted(by_cat, key=lambda c: (c == 0, -len(by_cat[c])))
    for cid in order:
        grp = by_cat[cid]
        name = cats.get(cid, {}).get("gu") if cid else "અન્ય (uncategorised)"
        en = cats.get(cid, {}).get("en", "Other") if cid else "Other"
        slug = f"cat-{cid:02d}"
        idx.append(f"| [{name} · {en}]({slug}.md) | {len(grp)} |")
        entries = []
        for rec in grp:
            head = rec["title"] or rec["title_en"] or rec["file"]
            lines = []
            if rec["title_en"] and rec["title"]:
                lines.append(f"_{rec['title_en']}_"); lines.append("")
            lines.append(rec["text"] or "_(text unavailable)_")
            if rec["date"]:
                lines += ["", f"_{rec['date']}_"]
            entries.append((head, lines))
        crumb = "[← iHariPrabodham](../../README.md) · [Prasang](README.md)"
        (d / f"{slug}.md").write_text(
            build_page(crumb, f"Prasang — {name} ({en})", f"_{len(entries)} prasang_", entries),
            encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  prasang: {len(data)} across {len(by_cat)} themes")
    return len(data)


# ── source: Kirtan ───────────────────────────────────────────────────────────
# Kirtan has no reader-HTML page (those URLs return the SPA shell); the lyric ships
# inline in the index `content`, prefixed with a collection label ("Bhaktisudha",
# "HariPrabodham શ્લોકો", …). Peel that label, then restore line breaks on the
# source's own markers (…. between lines, । danda) — the words themselves are unchanged.
def _kirtan_split(content):
    label = ""
    m = re.match(r"\s*([A-Za-z][A-Za-z ]*?)\s+(?=[^\x00-\x7f])", content)
    if m:
        label = m.group(1).strip(); content = content[m.end():]
    body = content.strip()
    body = re.sub(r"\.{3,}", "\n", body)          # …. line breaks
    body = re.sub(r"\s*।\s*", " ।\n", body)        # danda ends a verse line
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in body.split("\n")]
    return label or None, "\n".join(l for l in lines if l)


def do_kirtan(refetch=False):
    index = load("kirtan-index.json")
    data, entries = [], []
    for r in index:
        label, body = _kirtan_split(r["content"])
        rec = {"sid": r.get("sid"), "file": r["file"], "collection": label, "text": body}
        data.append(rec)
        first = body.split("\n", 1)[0][:44] if body else ""
        head = f"{r.get('sid')}. {first}" if first else f"Kirtan {r.get('sid')}"
        lines = []
        if label:
            lines += [f"_{label}_", ""]
        # render lyric lines as a hard-wrapped block
        lines.append("  \n".join(body.split("\n")) if body else "_(text unavailable)_")
        entries.append((head, lines))
    wj(DATA / "kirtan.json", data)
    # chunk into files of 60 for readability
    d = TEXT / "kirtan"; d.mkdir(parents=True, exist_ok=True)
    CH = 60
    idx = [CRUMB_ROOT, "", "# Kirtan", "",
           f"*Kirtan, shlok and dhun — {len(data)} lyrics.*", "", "| Part | Kirtan |", "|---|---:|"]
    for i in range(0, len(entries), CH):
        part = i // CH + 1
        chunk = entries[i:i + CH]
        idx.append(f"| [Part {part}](part-{part:02d}.md) | {len(chunk)} |")
        crumb = "[← iHariPrabodham](../../README.md) · [Kirtan](README.md)"
        (d / f"part-{part:02d}.md").write_text(
            build_page(crumb, f"Kirtan — Part {part}", f"_{len(chunk)} lyrics_", chunk),
            encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  kirtan: {len(data)}")
    return len(data)


# ── source: daily pravachan transcripts ──────────────────────────────────────
def do_transcripts(refetch=False):
    index = load("paramrut-index.json")
    files = [r["file"] for r in index]
    pages = fetch_html_many("paramrut", files, f"{SITE}/data/paramrut", refetch)
    by_year = collections.defaultdict(list)
    data = []
    for r in index:
        f = r["file"]
        title, body = html_body(pages.get(f, ""))
        ym = re.match(r"(\d{4})-(\d{2})-(\d{2})", f)
        dt = ym.group(0) if ym else None
        yr = ym.group(1) if ym else "undated"
        rec = {"file": f, "date": dt, "title": title, "text": body}
        data.append(rec); by_year[yr].append(rec)
    wj(DATA / "pravachan-transcripts.json", data)
    d = TEXT / "pravachan"; d.mkdir(parents=True, exist_ok=True)
    idx = [CRUMB_ROOT, "", "# Pravachan Transcripts", "",
           f"*Full transcripts of daily pravachan of Guruhari Prabodhjivan Swamiji — {len(data)} discourses.*",
           "", "| Year | Transcripts |", "|---|---:|"]
    for yr in sorted(by_year):
        grp = sorted(by_year[yr], key=lambda r: r["file"])
        idx.append(f"| [{yr}]({yr}.md) | {len(grp)} |")
        entries = []
        for rec in grp:
            head = " · ".join(x for x in [rec["date"], rec["title"]] if x) or rec["file"]
            entries.append((head, [rec["text"] or "_(text unavailable)_"]))
        crumb = "[← iHariPrabodham](../../README.md) · [Pravachan Transcripts](README.md)"
        (d / f"{yr}.md").write_text(
            build_page(crumb, f"Pravachan Transcripts — {yr}", f"_{len(entries)} discourses_", entries),
            encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  transcripts: {len(data)} across {len(by_year)} years")
    return len(data)


# ── source: discourse/darshan catalogue (metadata + links) ───────────────────
def do_discourses():
    recs = load("api-all-discourses.json")

    def U(s):
        return (s or "").replace("\\/", "/").strip() or None
    data = []
    by_cat = collections.defaultdict(list)
    for r in recs:
        rec = {"id": r.get("InfoId"), "title": (r.get("Title") or "").strip() or None,
               "date": r.get("InfoDate"), "place": r.get("Place"), "city": r.get("City"),
               "pradesh": r.get("Pradesh"), "topic": (r.get("SabhaDetail") or "").strip() or None,
               "series_id": r.get("VideoCategory"), "video": U(r.get("VideoUrl")),
               "audio": r.get("audio") or None}
        data.append(rec); by_cat[r.get("VideoCategory")].append(rec)
    wj(DATA / "discourses.json", data)
    d = TEXT / "discourses"; d.mkdir(parents=True, exist_ok=True)
    idx = [CRUMB_ROOT, "", "# Discourse & Darshan Catalogue", "",
           f"*The full catalogue the website lists — {len(data)} discourses across "
           f"{len(by_cat)} series. Text and links only; the videos stay on YouTube.*", "",
           "| Series | Records |", "|---|---:|"]
    for cid in sorted(by_cat, key=lambda c: -len(by_cat[c])):
        grp = sorted(by_cat[cid], key=lambda r: (r["date"] or "", r["id"] or 0))
        # infer a series name from the most common title stem
        stem = collections.Counter(re.sub(r"[\s#\d].*$", "", (r["title"] or "")) for r in grp).most_common(1)
        name = (stem[0][0] or f"Series {cid}").strip() or f"Series {cid}"
        slug = f"series-{cid:02d}"
        idx.append(f"| [{name}]({slug}.md) · {cid} | {len(grp)} |")
        entries = []
        for rec in grp:
            head = " · ".join(x for x in [rec["date"], rec["title"]] if x) or f"#{rec['id']}"
            lines = []
            loc = ", ".join(x for x in [rec["place"], rec["city"]] if x)
            meta = " · ".join(x for x in [loc, rec["pradesh"]] if x)
            if meta:
                lines += [f"_{meta}_", ""]
            if rec["topic"]:
                lines += [rec["topic"], ""]
            if rec["video"]:
                lines.append(f"▶ [Watch on YouTube]({rec['video']})")
            entries.append((head, lines))
        crumb = "[← iHariPrabodham](../../README.md) · [Discourse Catalogue](README.md)"
        (d / f"{slug}.md").write_text(
            build_page(crumb, f"{name} (series {cid})", f"_{len(entries)} discourses_", entries),
            encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  discourses: {len(data)} across {len(by_cat)} series")
    return len(data)


# ── source: vicharan + pravachan notes ───────────────────────────────────────
def do_vicharan():
    recs = load("worker-vicharan.json")
    data = []
    for r in recs:
        dt = r.get("infodate")
        dt = dt.get("date", "").split(" ")[0] if isinstance(dt, dict) else dt
        data.append({"id": r.get("infoid"), "date": dt, "place": r.get("place"),
                     "description": (r.get("shortdescguj") or "").strip() or None,
                     "video": (r.get("videourl") or "").strip() or None})
    wj(DATA / "vicharan.json", data)
    data.sort(key=lambda r: (r["date"] or "", r["id"] or 0))
    entries = []
    for r in data:
        head = " · ".join(x for x in [r["date"], r["place"]] if x) or f"#{r['id']}"
        lines = []
        if r["description"]:
            lines += [r["description"], ""]
        if r["video"]:
            lines.append(f"▶ [Watch]({r['video']})")
        entries.append((head, lines))
    (TEXT / "vicharan.md").write_text(
        build_page(CRUMB_ROOT, "Vicharan",
                   f"*Dated vicharan of Guruhari Prabodhjivan Swamiji — {len(data)} entries.*",
                   entries), encoding="utf-8")
    print(f"  vicharan: {len(data)}")
    return len(data)


def do_pravachan_notes():
    recs = load("worker-pravachan.json")
    data = []
    for r in recs:
        data.append({"id": r.get("PrvId"), "title": (r.get("PrvTitle") or "").strip() or None,
                     "date": r.get("PrvDate"), "place": r.get("PrvPlace"),
                     "info": (r.get("PrvInfo") or "").strip() or None,
                     "prasang": (r.get("PrvPrasang") or "").strip() or None,
                     "ref": (r.get("PrvRef") or "").strip() or None,
                     "video": (r.get("PrvVideoUrl") or "").strip() or None})
    wj(DATA / "pravachan-notes.json", data)
    data.sort(key=lambda r: (r["date"] or "", r["id"] or 0))
    entries = []
    for r in data:
        head = " · ".join(x for x in [r["date"], r["title"]] if x) or f"#{r['id']}"
        lines = []
        if r["place"]:
            lines += [f"_{r['place']}_", ""]
        for label, key in [("વિષય/પ્રસંગ", "info"), ("પ્રસંગ", "prasang"), ("સંદર્ભ", "ref")]:
            if r[key]:
                lines.append(r[key])
        if r["video"]:
            lines += ["", f"▶ [Watch]({r['video']})"]
        entries.append((head, lines))
    (TEXT / "pravachan-notes.md").write_text(
        build_page(CRUMB_ROOT, "Pravachan Notes",
                   f"*Discourse notes — subject, prasang and reference — {len(data)} entries.*",
                   entries), encoding="utf-8")
    print(f"  pravachan-notes: {len(data)}")
    return len(data)


# ── source: Brahm Ratna (curated pravachan collection) ───────────────────────
def do_brahmratna(refetch=False):
    """A curated granth: 100 pravachan of Guruhari Prabodhjivan Swamiji, hand-picked on
    the site. Metadata is embedded in the web app (mirrored to _source/…/brahmratna.json);
    the full transcript of each is the reader page under /data/paramrut/."""
    recs = load("brahmratna.json")
    files = [r["prvfile"] for r in recs]
    pages = fetch_html_many("paramrut", files, f"{SITE}/data/paramrut", refetch)
    data, entries = [], []
    for i, r in enumerate(recs, 1):
        f = r["prvfile"]
        title, body = html_body(pages.get(f, ""))
        rec = {"seq": i, "id": r.get("prvid"), "title": (r.get("prvtitle") or "").strip() or None,
               "date": r.get("prvdate"), "year": r.get("prvyear"),
               "place": (r.get("prvplace") or "").strip() or None,
               "info": (r.get("prvinfo") or "").strip() or None,
               "video": (r.get("prvvideourl") or "").strip() or None,
               "file": f, "text": body}
        data.append(rec)
        head = " · ".join(x for x in [r.get("prvdate"), rec["title"]] if x) or f"#{rec['id']}"
        lines = []
        meta = " · ".join(x for x in [rec["place"]] if x)
        if meta:
            lines += [f"_{meta}_", ""]
        if rec["info"]:
            lines += [rec["info"], ""]
        lines.append(rec["text"] or "_(transcript unavailable)_")
        if rec["video"]:
            lines += ["", f"▶ [Watch on YouTube]({rec['video']})"]
        entries.append((head, lines))
    wj(DATA / "brahm-ratna.json", data)
    sub = (f"*Brahm Ratna — {len(data)} curated pravachan of Guruhari Prabodhjivan Swamiji, "
           f"with full transcript and links.*")
    (TEXT / "brahm-ratna.md").write_text(
        build_page(CRUMB_ROOT, "Brahm Ratna", sub, entries), encoding="utf-8")
    print(f"  brahm-ratna: {len(data)} ({sum(1 for r in data if r['text'])} with transcript)")
    return len(data)


# ── source: Ambrish Upnishad ─────────────────────────────────────────────────
def _fix_nl(s):
    if not s:
        return s
    return re.sub(r"\\+n", "\n", s).replace("\\", "").strip()


def do_ambrish():
    """Ambrish Upnishad — a granth of Guruhari Hariprasad Swamishri's discourses, full
    text embedded in the web app (mirrored to _source/…/ambrishupnishad.json), grouped
    into prakaran (AU1-YYYY-NN)."""
    recs = load("ambrishupnishad.json")
    by_p = collections.OrderedDict()
    data = []
    for r in recs:
        pk = r.get("prakaran") or "?"
        rec = {"srno": r.get("srno"), "prakaran": pk,
               "title": _fix_nl(r.get("title")), "subtitle": _fix_nl(r.get("subtitle")),
               "date_gu": _fix_nl(r.get("gujdate")), "date_en": r.get("engdate"),
               "content": _fix_nl(r.get("content")), "desc": _fix_nl(r.get("desc")),
               "tags": [t.strip() for t in (r.get("tags") or "").split(",") if t.strip()],
               "year": r.get("year"), "file": r.get("filename")}
        data.append(rec); by_p.setdefault(pk, []).append(rec)
    wj(DATA / "ambrish-upnishad.json", data)
    d = TEXT / "ambrish-upnishad"; d.mkdir(parents=True, exist_ok=True)
    idx = [CRUMB_ROOT, "", "# Ambrish Upnishad", "",
           f"*Ambrish Upnishad — {len(data)} discourse-passages of Guruhari Hariprasad "
           f"Swamishri, in {len(by_p)} prakaran.*", "", "| Prakaran | Passages | |", "|---|---:|---|"]
    for pk, grp in by_p.items():
        slug = pk.lower()
        desc = (grp[0]["desc"] or "").split("\n")
        label = desc[-1] if desc else pk
        idx.append(f"| [{pk}]({slug}.md) | {len(grp)} | {label} |")
        entries = []
        for rec in grp:
            head = f"{rec['srno']}. {rec['title']}" if rec["title"] else f"#{rec['srno']}"
            lines = []
            meta = " · ".join(x for x in [rec["date_gu"], (rec["subtitle"] or '').replace('\n', ' — ')] if x)
            if meta:
                lines += [f"_{meta}_", ""]
            # content: numbered items separated by newlines → paragraphs
            body = "\n\n".join(p.strip() for p in (rec["content"] or "").split("\n") if p.strip())
            lines.append(body or "_(text unavailable)_")
            if rec["tags"]:
                lines += ["", "_" + " · ".join(rec["tags"]) + "_"]
            entries.append((head, lines))
        crumb = "[← iHariPrabodham](../../README.md) · [Ambrish Upnishad](README.md)"
        (d / f"{slug}.md").write_text(
            build_page(crumb, f"Ambrish Upnishad — {pk}", f"_{len(entries)} passages_", entries),
            encoding="utf-8")
    (d / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"  ambrish-upnishad: {len(data)} across {len(by_p)} prakaran")
    return len(data)


# ── main ─────────────────────────────────────────────────────────────────────
JOBS = collections.OrderedDict([
    ("brahm-ratna", do_brahmratna),
    ("ambrish-upnishad", do_ambrish),
    ("quotes", do_quotes), ("vato", do_swamini_vato), ("vachan", do_vachanamrut),
    ("prasang", do_prasang), ("kirtan", do_kirtan), ("transcripts", do_transcripts),
    ("discourses", do_discourses), ("vicharan", do_vicharan),
    ("pravachan-notes", do_pravachan_notes),
])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="*", help="subset of: " + ", ".join(JOBS))
    ap.add_argument("--refetch-html", action="store_true")
    args = ap.parse_args()
    for p in (DATA, TEXT):
        p.mkdir(parents=True, exist_ok=True)
    run = args.jobs or list(JOBS)
    counts = {}
    for j in run:
        fn = JOBS[j]
        counts[j] = fn(args.refetch_html) if j in ("prasang", "kirtan", "transcripts", "brahm-ratna") else fn()
    # manifest
    man = {"source": {"site": SITE, "fetched": date.today().isoformat()},
           "counts": counts, "total": sum(counts.values())}
    if (DATA / "index.json").exists() and not args.jobs:
        pass
    wj(DATA / "index.json", man)
    print("done:", counts)


if __name__ == "__main__":
    main()
