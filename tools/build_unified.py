#!/usr/bin/env python3
"""Build the unified, deduplicated, tagged corpus from both sources.

Reads the already-clean per-collection JSON (app corpus in data/*.json, website
corpus in data/ihariprabodham/*.json), removes the four overlaps by keeping the
richer copy, applies the canonical theme taxonomy (tools/taxonomy.py), and writes:

    unified/text/   readable section pages, foldered type -> work -> section,
                    each with YAML frontmatter (Obsidian Properties) + inline
                    per-item theme tags + a table of contents
    unified/data/   per-item JSON with structural + theme tags (the query layer)
    unified/tags/   one page per theme, linking to items across every collection

Gujarati text is copied verbatim from the source JSON — never re-parsed or retyped.
"""
import collections, json, re, unicodedata
from pathlib import Path
import taxonomy as TX

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "unified"
TEXT = OUT / "text"
DATA = OUT / "data"
TAGS = OUT / "tags"
MARK = "<!-- nav:generated -->"

# theme slug -> {en, gu}
TXMAP = {t["slug"]: t for t in TX.build_taxonomy().values()}
# every (collection, item_ref, heading) tagged with a theme, for tag pages
TAG_INDEX = collections.defaultdict(list)   # slug -> [(coll_label, link, heading)]


def A(text, seen):
    out = []
    for ch in text.strip().lower():
        if ch == " ":
            out.append("-")
        elif ch in "-_" or unicodedata.category(ch)[0] in ("L", "N", "M"):
            out.append(ch)
    a = "".join(out); n = seen[a]; seen[a] += 1
    return a if n == 0 else f"{a}-{n}"


def yaml_val(v):
    if isinstance(v, list):
        return "[" + ", ".join(yaml_val(x) for x in v) + "]"
    if v is None:
        return '""'
    s = str(v)
    if re.search(r'[:#\[\]{}",\']', s) or s != s.strip():
        return '"' + s.replace('"', '\\"') + '"'
    return s


def frontmatter(d):
    lines = ["---"]
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], str) and k in ("tags", "aliases"):
            lines.append(f"{k}:")
            lines += [f"  - {x}" for x in v]
        else:
            lines.append(f"{k}: {yaml_val(v)}")
    lines.append("---")
    return "\n".join(lines)


def theme_line(slugs):
    if not slugs:
        return None
    return "🏷️ " + " · ".join(f"*{TXMAP[s]['gu']}*" for s in slugs if s in TXMAP)


def obsidian_tags(base, themes):
    return base + [f"theme/{s}" for s in themes]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def page(path, fm, title, subtitle, entries, crumb, coll_label, rel_from_tag):
    """entries: list of (heading, [lines], themes). Records tag index + writes file."""
    seen = collections.defaultdict(int)
    toc, body = [], []
    for heading, lines, themes in entries:
        anc = A(heading, seen)
        toc.append(f"- [{heading}](#{anc})")
        body.append(f"\n## {heading}\n")
        tl = theme_line(themes)
        if tl:
            body.append(tl + "\n")
        body += lines
        body.append("\n---")
        for s in themes:
            TAG_INDEX[s].append((coll_label, f"{rel_from_tag}#{anc}", heading))
    open_toc = len(entries) <= 25
    out = [frontmatter(fm), "", crumb, "", f"# {title}", "", subtitle, "", MARK, "",
           f'<details{" open" if open_toc else ""}>',
           f"<summary><b>Contents</b> — {len(entries)} entries</summary>", "",
           *toc, "", "</details>", "", "---", *body, ""]
    write(path, "\n".join(out) + "\n")


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def paras(text):
    if not text:
        return "_(text unavailable)_"
    return "\n\n".join(p.strip() for p in str(text).split("\n") if p.strip()) or "_(text unavailable)_"


def crumb(*parts):
    return " · ".join(parts)

C_HUB = "[← Unified corpus](%s/README.md)"


# ── GRANTH: Swamini Vato ─────────────────────────────────────────────────────
def swamini_vato():
    recs = load("data/swamini-vato.json")
    topics = load("data/topics.json")
    tindex = {t["id"]: set(t["vat_ids"]) for t in topics}
    by_p = collections.defaultdict(list)
    for r in recs:
        by_p[r["prakaran"]].append(r)
    data = []
    idx_rows = []
    for p in sorted(by_p):
        grp = sorted(by_p[p], key=lambda r: r["vat_no"] or 0)
        pname = grp[0].get("prakaran_name_gu") or ""
        entries = []
        for r in grp:
            themes = TX.vato_themes(r["vat_id"], tindex)
            t = r["text"]
            lines = [paras(t.get("gu"))]
            if t.get("hi"):
                lines += ["", "**हिन्दी**", "", paras(t["hi"])]
            if t.get("en"):
                lines += ["", "**English**", "", paras(t["en"])]
            fn = (r.get("footnotes") or {}).get("gu") or []
            if fn:
                lines += ["", "**Notes**", ""]
                for f in fn:
                    lines.append(f"{f['n']}. **{f['term']}** — {f['meaning']}" if f.get("term") else f"- {f['meaning']}")
            head = f"Vato {r['vat_no']}"
            entries.append((head, lines, themes))
            data.append({"id": r["vat_id"], "type": "granth", "work": "swamini-vato",
                         "prakaran": p, "vat_no": r["vat_no"], "title_gu": r.get("title_gu"),
                         "text": t, "footnotes": r.get("footnotes"), "themes": themes,
                         "source": "paramrut-app", "lang": [k for k in ("gu", "hi", "en") if t.get(k)]})
        fm = {"type": "granth", "work": "swamini-vato", "prakaran": p,
              "prakaran_name_gu": pname, "count": len(grp), "source": "paramrut-app",
              "tags": ["type/granth", "granth/swamini-vato"]}
        page(TEXT / "granth/swamini-vato" / f"prakaran-{p:02d}.md", fm,
             f"Swamini Vato — Prakaran {p}", f"_{pname}_  \n_{len(grp)} vato_",
             entries, crumb("[← Granth](../README.md)", "[Swamini Vato](README.md)"),
             f"Swamini Vato · Prakaran {p}", f"text/granth/swamini-vato/prakaran-{p:02d}.md")
        idx_rows.append(f"| [Prakaran {p}](prakaran-{p:02d}.md) | {pname} | {len(grp)} |")
    wj("swamini-vato.json", data)
    write(TEXT / "granth/swamini-vato/README.md",
          "\n".join([frontmatter({"type": "granth", "work": "swamini-vato",
                                  "tags": ["type/granth", "granth/swamini-vato"]}), "",
                     crumb("[← Granth](../README.md)"), "", "# Swamini Vato", "",
                     f"_{len(recs)} vato · 16 prakaran · Gunatitanand Swami_", "",
                     "| Prakaran | Subject | Vato |", "|---|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


# ── GRANTH: Vachanamrut ──────────────────────────────────────────────────────
def vachanamrut():
    recs = load("data/vachanamrut.json")
    order = ["Gadhada Pratham", "Sarangpur", "Kariyani", "Loya", "Panchala",
             "Gadhada Madhya", "Vartal", "Amadavad", "Gadhada Antya", "Jetalpur",
             "Kariyani (misc)", "Ashirvad"]
    by_s = collections.defaultdict(list)
    for r in recs:
        by_s[r["section"]].append(r)
    data, idx_rows = [], []
    for sec in order:
        if sec not in by_s:
            continue
        grp = sorted(by_s[sec], key=lambda r: r["number"])
        slug = sec.lower().replace(" ", "-").replace("(", "").replace(")", "")
        entries = []
        for r in grp:
            lines = [paras(r["text"])]
            head = f"{sec} {r['number']}" + (f" — {r['title_gu']}" if r.get("title_gu") else "")
            entries.append((head, lines, []))
            data.append({"id": r["id"], "type": "granth", "work": "vachanamrut",
                         "section": sec, "number": r["number"], "title_gu": r.get("title_gu"),
                         "tithi": r.get("tithi"), "date": r.get("date"), "weekday": r.get("weekday"),
                         "text": r["text"], "highlights": r.get("highlights", []),
                         "themes": [], "source": "paramrut-app", "lang": ["gu"]})
        fm = {"type": "granth", "work": "vachanamrut", "section": sec, "count": len(grp),
              "source": "paramrut-app", "tags": ["type/granth", "granth/vachanamrut"]}
        page(TEXT / "granth/vachanamrut" / f"{slug}.md", fm, f"Vachanamrut — {sec}",
             f"_{len(grp)} vachanamrut_", entries,
             crumb("[← Granth](../README.md)", "[Vachanamrut](README.md)"),
             f"Vachanamrut · {sec}", f"../../../granth/vachanamrut/{slug}.md")
        idx_rows.append(f"| [{sec}]({slug}.md) | {len(grp)} |")
    wj("vachanamrut.json", data)
    write(TEXT / "granth/vachanamrut/README.md",
          "\n".join([frontmatter({"type": "granth", "work": "vachanamrut",
                                  "tags": ["type/granth", "granth/vachanamrut"]}), "",
                     crumb("[← Granth](../README.md)"), "", "# Vachanamrut", "",
                     f"_{len(recs)} vachanamrut · 12 sections · Bhagwan Swaminarayan_", "",
                     "| Section | Count |", "|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


# ── GRANTH: Anirdeshi Amrut ──────────────────────────────────────────────────
def anirdeshi():
    recs = load("data/anirdeshi-amrut.json")
    by = collections.OrderedDict()
    for r in recs:
        by.setdefault((r["kalash"], r["achaman"]), []).append(r)
    data, idx_rows = [], []
    for (kalash, achaman), grp in by.items():
        grp = sorted(grp, key=lambda r: (r.get("date") or "", r["id"]))
        slug = re.sub(r"[^0-9]", "", kalash) + "-" + re.sub(r"[^0-9]", "", achaman)
        slug = f"kalash-{slug}" if slug.strip("-") else f"grp-{len(idx_rows)+1}"
        entries = []
        for r in grp:
            nat = r.get("tags") or []
            lines = []
            if r.get("date"):
                lines.append(f"_{r['date']}_")
            if r.get("title") and r["title"] != kalash + ", " + achaman:
                pass
            lines.append(paras(r["text"]))
            head = r.get("date") or f"#{r['id']}"
            # native gujarati tags shown, but canonical themes empty (free-form)
            entries.append((head, ([f"_{' · '.join(nat)}_", ""] + lines) if nat else lines, []))
            data.append({"id": r["id"], "type": "granth", "work": "anirdeshi-amrut",
                         "kalash": kalash, "achaman": achaman, "date": r.get("date"),
                         "native_tags": nat, "text": r["text"], "themes": [],
                         "source": "paramrut-app", "lang": ["gu"]})
        fm = {"type": "granth", "work": "anirdeshi-amrut", "kalash": kalash, "achaman": achaman,
              "count": len(grp), "source": "paramrut-app",
              "tags": ["type/granth", "granth/anirdeshi-amrut"]}
        page(TEXT / "granth/anirdeshi-amrut" / f"{slug}.md", fm,
             f"Anirdeshi Amrut — {kalash}, {achaman}", f"_{len(grp)} sabha_", entries,
             crumb("[← Granth](../README.md)", "[Anirdeshi Amrut](README.md)"),
             f"Anirdeshi Amrut · {kalash} {achaman}", f"../../../granth/anirdeshi-amrut/{slug}.md")
        idx_rows.append(f"| [{kalash}, {achaman}]({slug}.md) | {len(grp)} |")
    wj("anirdeshi-amrut.json", data)
    write(TEXT / "granth/anirdeshi-amrut/README.md",
          "\n".join([frontmatter({"type": "granth", "work": "anirdeshi-amrut",
                                  "tags": ["type/granth", "granth/anirdeshi-amrut"]}), "",
                     crumb("[← Granth](../README.md)"), "", "# Anirdeshi Amrut", "",
                     f"_{len(recs)} sabha · Guruhari Hariprasad Swamishri_", "",
                     "| Kalash · Achaman | Sabha |", "|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


# ── GRANTH: Ambrish Upnishad ─────────────────────────────────────────────────
def ambrish():
    recs = load("data/ihariprabodham/ambrish-upnishad.json")
    by = collections.OrderedDict()
    for r in recs:
        by.setdefault(r["prakaran"], []).append(r)
    data, idx_rows = [], []
    for pk, grp in by.items():
        slug = pk.lower()
        entries = []
        for r in grp:
            lines = []
            meta = " · ".join(x for x in [r.get("date_gu"), (r.get("subtitle") or "").replace("\n", " — ")] if x)
            if meta:
                lines += [f"_{meta}_", ""]
            lines.append(paras(r.get("content")))
            head = f"{r['srno']}. {r['title']}" if r.get("title") else f"#{r['srno']}"
            entries.append((head, lines, []))
            data.append({"id": r["srno"], "type": "granth", "work": "ambrish-upnishad",
                         "prakaran": pk, "title": r.get("title"), "date": r.get("date_en"),
                         "text": r.get("content"), "native_tags": r.get("tags", []),
                         "themes": [], "source": "ihariprabodham", "lang": ["gu"]})
        fm = {"type": "granth", "work": "ambrish-upnishad", "prakaran": pk, "count": len(grp),
              "source": "ihariprabodham", "tags": ["type/granth", "granth/ambrish-upnishad"]}
        page(TEXT / "granth/ambrish-upnishad" / f"{slug}.md", fm,
             f"Ambrish Upnishad — {pk}", f"_{len(grp)} passages_", entries,
             crumb("[← Granth](../README.md)", "[Ambrish Upnishad](README.md)"),
             f"Ambrish Upnishad · {pk}", f"../../../granth/ambrish-upnishad/{slug}.md")
        idx_rows.append(f"| [{pk}]({slug}.md) | {len(grp)} |")
    wj("ambrish-upnishad.json", data)
    write(TEXT / "granth/ambrish-upnishad/README.md",
          "\n".join([frontmatter({"type": "granth", "work": "ambrish-upnishad",
                                  "tags": ["type/granth", "granth/ambrish-upnishad"]}), "",
                     crumb("[← Granth](../README.md)"), "", "# Ambrish Upnishad", "",
                     f"_{len(recs)} passages · {len(by)} prakaran · Guruhari Hariprasad Swamishri_", "",
                     "| Prakaran | Passages |", "|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


# ── GRANTH: Brahm Ratna, Shikshapatri, Kirtan ────────────────────────────────
def brahmratna():
    recs = load("data/ihariprabodham/brahm-ratna.json")
    entries, data = [], []
    for r in sorted(recs, key=lambda r: (r.get("date") or "", r.get("seq") or 0)):
        lines = []
        if r.get("place"):
            lines += [f"_{r['place']}_", ""]
        if r.get("info"):
            lines += [r["info"], ""]
        lines.append(paras(r.get("text")))
        if r.get("video"):
            lines += ["", f"▶ [Watch]({r['video']})"]
        head = " · ".join(x for x in [r.get("date"), r.get("title")] if x) or f"#{r.get('id')}"
        entries.append((head, lines, []))
        data.append({"id": r.get("id"), "type": "granth", "work": "brahm-ratna",
                     "title": r.get("title"), "date": r.get("date"), "place": r.get("place"),
                     "text": r.get("text"), "video": r.get("video"), "themes": [],
                     "source": "ihariprabodham", "lang": ["gu"]})
    wj("brahm-ratna.json", data)
    fm = {"type": "granth", "work": "brahm-ratna", "count": len(data), "source": "ihariprabodham",
          "tags": ["type/granth", "granth/brahm-ratna"]}
    page(TEXT / "granth/brahm-ratna.md", fm, "Brahm Ratna",
         f"_{len(data)} curated pravachan · Guruhari Prabodhjivan Swamiji_", entries,
         crumb("[← Granth](README.md)"), "Brahm Ratna", "../granth/brahm-ratna.md")
    return len(data)


def shikshapatri():
    recs = load("data/shikshapatri.json")
    entries, data = [], []
    for r in sorted(recs, key=lambda r: r["number"]):
        lines = []
        if r.get("sanskrit"):
            lines += ["\n".join("> " + l for l in r["sanskrit"].split("\n")), ""]
        if r.get("gujarati"):
            lines += [paras(r["gujarati"])]
        if r.get("hindi"):
            lines += ["", "**हिन्दी**", "", paras(r["hindi"])]
        head = f"Shlok {r['number']}"
        entries.append((head, lines, []))
        data.append({"id": r["number"], "type": "granth", "work": "shikshapatri",
                     "number": r["number"], "sanskrit": r.get("sanskrit"),
                     "gujarati": r.get("gujarati"), "hindi": r.get("hindi"),
                     "selected": r.get("selected"), "themes": [], "source": "paramrut-app",
                     "lang": ["sa", "gu", "hi"]})
    wj("shikshapatri.json", data)
    fm = {"type": "granth", "work": "shikshapatri", "count": len(data), "source": "paramrut-app",
          "tags": ["type/granth", "granth/shikshapatri"]}
    page(TEXT / "granth/shikshapatri.md", fm, "Shikshapatri",
         f"_{len(data)} shlok · Sanskrit · Gujarati · Hindi_", entries,
         crumb("[← Granth](README.md)"), "Shikshapatri", "../granth/shikshapatri.md")
    return len(data)


def kirtan():
    recs = load("data/ihariprabodham/kirtan.json")
    CH = 60
    data = []
    for r in recs:
        data.append({"id": r.get("sid"), "type": "granth", "work": "kirtan",
                     "collection": r.get("collection"), "text": r.get("text"),
                     "themes": [], "source": "ihariprabodham", "lang": ["gu"]})
    wj("kirtan.json", data)
    idx_rows = []
    for i in range(0, len(recs), CH):
        part = i // CH + 1
        grp = recs[i:i + CH]
        entries = []
        for r in grp:
            body = r.get("text") or ""
            first = body.split("\n", 1)[0][:44]
            head = f"{r.get('sid')}. {first}" if first else f"Kirtan {r.get('sid')}"
            lines = []
            if r.get("collection"):
                lines += [f"_{r['collection']}_", ""]
            lines.append("  \n".join(body.split("\n")) if body else "_(text unavailable)_")
            entries.append((head, lines, []))
        fm = {"type": "granth", "work": "kirtan", "part": part, "count": len(grp),
              "source": "ihariprabodham", "tags": ["type/granth", "granth/kirtan"]}
        page(TEXT / "granth/kirtan" / f"part-{part:02d}.md", fm, f"Kirtan — Part {part}",
             f"_{len(grp)} kirtan_", entries,
             crumb("[← Granth](../README.md)", "[Kirtan](README.md)"),
             f"Kirtan · Part {part}", f"../../../granth/kirtan/part-{part:02d}.md")
        idx_rows.append(f"| [Part {part}](part-{part:02d}.md) | {len(grp)} |")
    write(TEXT / "granth/kirtan/README.md",
          "\n".join([frontmatter({"type": "granth", "work": "kirtan",
                                  "tags": ["type/granth", "granth/kirtan"]}), "",
                     crumb("[← Granth](../README.md)"), "", "# Kirtan", "",
                     f"_{len(recs)} kirtan · shlok · aarti_", "",
                     "| Part | Kirtan |", "|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


# ── PRASANG (themed) ─────────────────────────────────────────────────────────
def prasang():
    recs = load("data/ihariprabodham/prasang.json")
    by = collections.defaultdict(list)
    for r in recs:
        slug = TX.prasang_theme(r.get("category_id")) or "_untagged"
        by[slug].append(r)
    data, idx_rows = [], []
    order = sorted(by, key=lambda s: (s == "_untagged", -len(by[s])))
    for slug in order:
        grp = by[slug]
        themes = [slug] if slug != "_untagged" else []
        name = TXMAP[slug]["gu"] if slug in TXMAP else "અન્ય (untagged)"
        en = TXMAP[slug]["en"] if slug in TXMAP else "Untagged"
        entries = []
        for r in grp:
            lines = []
            if r.get("title_en") and r.get("title"):
                lines += [f"_{r['title_en']}_", ""]
            lines.append(paras(r.get("text")))
            if r.get("date"):
                lines += ["", f"_{r['date']}_"]
            head = r.get("title") or r.get("title_en") or r.get("file")
            entries.append((head, lines, themes))
            data.append({"id": r.get("id"), "type": "prasang", "title": r.get("title"),
                         "title_en": r.get("title_en"), "date": r.get("date"),
                         "text": r.get("text"), "themes": themes, "source": "ihariprabodham",
                         "lang": ["gu"]})
        fm = {"type": "prasang", "theme": slug, "theme_gu": name, "count": len(grp),
              "source": "ihariprabodham", "tags": ["type/prasang"] + ([f"theme/{slug}"] if themes else [])}
        page(TEXT / "prasang" / f"{slug}.md", fm, f"Prasang — {name} ({en})",
             f"_{len(grp)} prasang_", entries, crumb("[← Prasang](README.md)"),
             f"Prasang · {name}", f"text/prasang/{slug}.md")
        idx_rows.append((en, f"| [{name} · {en}]({slug}.md) | {len(grp)} |"))
    wj("prasang.json", data)
    idx_rows.sort()
    write(TEXT / "prasang/README.md",
          "\n".join([frontmatter({"type": "prasang", "tags": ["type/prasang"]}), "",
                     C_HUB % "../..", "", "# Prasang", "",
                     f"_{len(recs)} incident-stories · by theme_", "",
                     "| Theme | Prasang |", "|---|---:|", *[r for _, r in idx_rows], ""]) + "\n")
    return len(data)


# ── PRAVACHAN (transcripts, hari-amrut, catalogue) ───────────────────────────
def transcripts():
    recs = load("data/ihariprabodham/pravachan-transcripts.json")
    by = collections.defaultdict(list)
    for r in recs:
        yr = (r.get("date") or "undated")[:4]
        by[yr].append(r)
    data, idx_rows = [], []
    for yr in sorted(by):
        grp = sorted(by[yr], key=lambda r: r["file"])
        entries = []
        for r in grp:
            head = " · ".join(x for x in [r.get("date"), r.get("title")] if x) or r["file"]
            entries.append((head, [paras(r.get("text"))], []))
            data.append({"id": r["file"], "type": "pravachan", "work": "transcripts",
                         "date": r.get("date"), "title": r.get("title"), "text": r.get("text"),
                         "themes": [], "source": "ihariprabodham", "lang": ["gu"]})
        fm = {"type": "pravachan", "work": "transcripts", "year": yr, "count": len(grp),
              "source": "ihariprabodham", "tags": ["type/pravachan", "pravachan/transcripts"]}
        page(TEXT / "pravachan/transcripts" / f"{yr}.md", fm,
             f"Pravachan Transcripts — {yr}", f"_{len(grp)} discourses_", entries,
             crumb("[← Pravachan](../README.md)", "[Transcripts](README.md)"),
             f"Transcript · {yr}", f"../../../pravachan/transcripts/{yr}.md")
        idx_rows.append(f"| [{yr}]({yr}.md) | {len(grp)} |")
    wj("pravachan-transcripts.json", data)
    write(TEXT / "pravachan/transcripts/README.md",
          "\n".join([frontmatter({"type": "pravachan", "work": "transcripts",
                                  "tags": ["type/pravachan", "pravachan/transcripts"]}), "",
                     crumb("[← Pravachan](../README.md)"), "", "# Pravachan Transcripts", "",
                     f"_{len(recs)} daily discourses · Guruhari Prabodhjivan Swamiji_", "",
                     "| Year | Transcripts |", "|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


def hari_amrut():
    recs = load("data/ihariprabodham/pravachan-notes.json")
    recs = sorted(recs, key=lambda r: (r.get("date") or "", r.get("id") or 0))
    entries, data = [], []
    for r in recs:
        lines = []
        if r.get("place"):
            lines += [f"_{r['place']}_", ""]
        for k in ("info", "prasang", "ref"):
            if r.get(k):
                lines.append(r[k])
        if r.get("video"):
            lines += ["", f"▶ [Watch]({r['video']})"]
        head = " · ".join(x for x in [r.get("date"), r.get("title")] if x) or f"#{r.get('id')}"
        entries.append((head, lines, []))
        data.append({"id": r.get("id"), "type": "pravachan", "work": "hari-amrut",
                     "title": r.get("title"), "date": r.get("date"), "place": r.get("place"),
                     "info": r.get("info"), "themes": [], "source": "ihariprabodham", "lang": ["gu"]})
    wj("hari-amrut.json", data)
    fm = {"type": "pravachan", "work": "hari-amrut", "count": len(data), "source": "ihariprabodham",
          "tags": ["type/pravachan", "pravachan/hari-amrut"]}
    page(TEXT / "pravachan/hari-amrut.md", fm, "Hari Amrut",
         f"_{len(data)} discourse notes · subject · prasang · reference_", entries,
         crumb("[← Pravachan](README.md)"), "Hari Amrut", "../pravachan/hari-amrut.md")
    return len(data)


def catalogue():
    recs = load("data/ihariprabodham/discourses.json")
    by = collections.defaultdict(list)
    for r in recs:
        by[r.get("series_id")].append(r)
    data, idx_rows = [], []
    for cid in sorted(by, key=lambda c: -len(by[c])):
        grp = sorted(by[cid], key=lambda r: (r.get("date") or "", r.get("id") or 0))
        stem = collections.Counter(re.sub(r"[\s#\d].*$", "", (r.get("title") or "")) for r in grp).most_common(1)
        name = (stem[0][0] or f"Series {cid}").strip() or f"Series {cid}"
        slug = f"series-{cid:02d}"
        entries = []
        for r in grp:
            lines = []
            loc = ", ".join(x for x in [r.get("place"), r.get("city")] if x)
            meta = " · ".join(x for x in [loc, r.get("pradesh")] if x)
            if meta:
                lines += [f"_{meta}_", ""]
            if r.get("topic"):
                lines += [r["topic"], ""]
            if r.get("video"):
                lines.append(f"▶ [Watch]({r['video']})")
            head = " · ".join(x for x in [r.get("date"), r.get("title")] if x) or f"#{r.get('id')}"
            entries.append((head, lines, []))
            data.append({"id": r.get("id"), "type": "pravachan", "work": "catalogue",
                         "series": name, "title": r.get("title"), "date": r.get("date"),
                         "topic": r.get("topic"), "video": r.get("video"),
                         "themes": [], "source": "ihariprabodham", "lang": ["gu"]})
        fm = {"type": "pravachan", "work": "catalogue", "series": name, "count": len(grp),
              "source": "ihariprabodham", "tags": ["type/pravachan", "pravachan/catalogue"]}
        page(TEXT / "pravachan/catalogue" / f"{slug}.md", fm, f"{name} (series {cid})",
             f"_{len(grp)} discourses · text + links_", entries,
             crumb("[← Pravachan](../README.md)", "[Catalogue](README.md)"),
             f"Catalogue · {name}", f"../../../pravachan/catalogue/{slug}.md")
        idx_rows.append(f"| [{name}]({slug}.md) | {len(grp)} |")
    wj("discourses.json", data)
    write(TEXT / "pravachan/catalogue/README.md",
          "\n".join([frontmatter({"type": "pravachan", "work": "catalogue",
                                  "tags": ["type/pravachan", "pravachan/catalogue"]}), "",
                     crumb("[← Pravachan](../README.md)"), "", "# Discourse Catalogue", "",
                     f"_{len(recs)} discourses · {len(by)} series · text + YouTube links_", "",
                     "| Series | Records |", "|---|---:|", *idx_rows, ""]) + "\n")
    return len(data)


# ── PARAVANI (quotes, merged) · PARISISHTH · VICHARAN ────────────────────────
def paravani():
    app = load("data/quotes.json")
    web = {r["number"]: r for r in load("data/ihariprabodham/quotes.json")}
    entries, data = [], []
    for r in app:
        w = web.get(r["number"], {})
        lines = [r["quote"], ""]
        meta = " · ".join(x for x in [r.get("guru"), r.get("date_gu"), r.get("place")] if x)
        if meta:
            lines.append(f"_{meta}_")
        head = f"{r['number']}. " + (r["quote"][:46] + "…" if len(r["quote"]) > 48 else r["quote"])
        entries.append((head, lines, []))
        data.append({"id": r["number"], "type": "paravani", "quote": r["quote"],
                     "guru": r.get("guru"), "guru_raw": r.get("guru_raw"),
                     "date_gu": r.get("date_gu"), "date_en": w.get("englishdate"),
                     "place": r.get("place"), "themes": [], "source": "merged", "lang": ["gu"]})
    wj("paravani.json", data)
    fm = {"type": "paravani", "count": len(data), "source": "merged",
          "tags": ["type/paravani"]}
    page(TEXT / "paravani.md", fm, "Guruhari Paravani",
         f"_{len(data)} quotes · Guruhari Prabodhjivan Swamiji · Guruhari Hariprasad Swamishri_",
         entries, C_HUB % "..", "Paravani", "./paravani.md")
    return len(data)


def parisishth():
    recs = load("data/parisishth.json")
    entries, data = [], []
    for r in sorted(recs, key=lambda r: r["id"]):
        lines = []
        if r.get("title_translit"):
            lines += [f"_{r['title_translit']}_", ""]
        lines.append(paras(r.get("text")))
        head = r.get("title_gu") or r.get("title_translit") or f"#{r['id']}"
        entries.append((head, lines, []))
        data.append({"id": r["id"], "type": "parisishth", "title_gu": r.get("title_gu"),
                     "title_translit": r.get("title_translit"), "text": r.get("text"),
                     "themes": [], "source": "paramrut-app", "lang": ["gu"]})
    wj("parisishth.json", data)
    fm = {"type": "parisishth", "count": len(data), "source": "paramrut-app",
          "tags": ["type/parisishth"]}
    page(TEXT / "parisishth.md", fm, "Parisishth",
         f"_{len(data)} entries · glossary & biographies_", entries,
         C_HUB % "..", "Parisishth", "./parisishth.md")
    return len(data)


def vicharan():
    recs = load("data/ihariprabodham/vicharan.json")
    recs = sorted(recs, key=lambda r: (r.get("date") or "", r.get("id") or 0))
    entries, data = [], []
    for r in recs:
        lines = []
        if r.get("description"):
            lines += [r["description"], ""]
        if r.get("video"):
            lines.append(f"▶ [Watch]({r['video']})")
        head = " · ".join(x for x in [r.get("date"), r.get("place")] if x) or f"#{r.get('id')}"
        entries.append((head, lines, []))
        data.append({"id": r.get("id"), "type": "vicharan", "date": r.get("date"),
                     "place": r.get("place"), "description": r.get("description"),
                     "themes": [], "source": "ihariprabodham", "lang": ["gu"]})
    wj("vicharan.json", data)
    fm = {"type": "vicharan", "count": len(data), "source": "ihariprabodham",
          "tags": ["type/vicharan"]}
    page(TEXT / "vicharan.md", fm, "Vicharan",
         f"_{len(data)} dated darshan · Guruhari Prabodhjivan Swamiji_", entries,
         C_HUB % "..", "Vicharan", "text/vicharan.md")
    return len(data)


def wj(name, obj):
    (DATA).mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ── tag pages + hub READMEs ──────────────────────────────────────────────────
def tag_pages():
    TAGS.mkdir(parents=True, exist_ok=True)
    rows = []
    for slug in sorted(TAG_INDEX, key=lambda s: -len(TAG_INDEX[s])):
        items = TAG_INDEX[slug]
        t = TXMAP.get(slug, {"gu": slug, "en": slug})
        by_coll = collections.defaultdict(list)
        for coll, link, heading in items:
            by_coll[coll].append((link, heading))
        body = [frontmatter({"type": "tag", "theme": slug, "theme_gu": t["gu"],
                             "count": len(items), "tags": [f"theme/{slug}"]}), "",
                "[← All themes](README.md)", "", f"# {t['gu']} · {t['en']}", "",
                f"_{len(items)} passages tagged **{t['en']}**, across the corpus._", ""]
        for coll in sorted(by_coll):
            body.append(f"\n### {coll}\n")
            for link, heading in by_coll[coll]:
                body.append(f"- [{heading}](../{link})")
        write(TAGS / f"{slug}.md", "\n".join(body) + "\n")
        rows.append(f"| [{t['gu']} · {t['en']}]({slug}.md) | {len(items)} |")
    write(TAGS / "README.md",
          "\n".join([frontmatter({"type": "tag-index", "themes": len(TAG_INDEX)}), "",
                     C_HUB % "..", "", "# Themes", "",
                     f"_{len(TAG_INDEX)} themes · browse the corpus by subject._", "",
                     "| Theme | Passages |", "|---|---:|", *rows, ""]) + "\n")
    return len(TAG_INDEX)


def granth_readme(counts):
    rows = [
        ("Swamini Vato", "swamini-vato/README.md", counts["swamini-vato"]),
        ("Vachanamrut", "vachanamrut/README.md", counts["vachanamrut"]),
        ("Anirdeshi Amrut", "anirdeshi-amrut/README.md", counts["anirdeshi-amrut"]),
        ("Ambrish Upnishad", "ambrish-upnishad/README.md", counts["ambrish-upnishad"]),
        ("Brahm Ratna", "brahm-ratna.md", counts["brahm-ratna"]),
        ("Shikshapatri", "shikshapatri.md", counts["shikshapatri"]),
        ("Kirtan", "kirtan/README.md", counts["kirtan"]),
    ]
    lines = [frontmatter({"type": "granth", "tags": ["type/granth"]}), "",
             C_HUB % "../..", "", "# Granth", "", "_The scriptures._", "",
             "| Granth | Records |", "|---|---:|"]
    lines += [f"| [{n}]({p}) | {c} |" for n, p, c in rows]
    write(TEXT / "granth/README.md", "\n".join(lines) + "\n")


def pravachan_readme(counts):
    lines = [frontmatter({"type": "pravachan", "tags": ["type/pravachan"]}), "",
             C_HUB % "../..", "", "# Pravachan", "", "_Discourses, transcripts and catalogue._", "",
             "| | Records |", "|---|---:|",
             f"| [Transcripts](transcripts/README.md) | {counts['pravachan-transcripts']} |",
             f"| [Hari Amrut](hari-amrut.md) | {counts['hari-amrut']} |",
             f"| [Discourse Catalogue](catalogue/README.md) | {counts['discourses']} |"]
    write(TEXT / "pravachan/README.md", "\n".join(lines) + "\n")


def hub(counts, nthemes):
    total = sum(counts.values())
    lines = [frontmatter({"title": "Paramrut Corpus", "tags": ["corpus"]}), "",
             "# Paramrut — Unified Corpus", "",
             f"**{total:,} records** of the HariPrabodham sampraday's scripture, prasang, "
             "pravachan and paravani — deduplicated from the Paramrut app and ihariprabodham.org, "
             "structured, and tagged.", "",
             "The text is unchanged. Structure, YAML tags (Obsidian-ready) and a theme index are added.", "",
             "## Read", "",
             "| Section | Contents |", "|---|---|",
             f"| 📖 **[Granth](text/granth/README.md)** | Swamini Vato, Vachanamrut, Anirdeshi Amrut, Ambrish Upnishad, Brahm Ratna, Shikshapatri, Kirtan |",
             f"| 📿 **[Prasang](text/prasang/README.md)** | {counts['prasang']} incident-stories, by theme |",
             f"| 🗣️ **[Pravachan](text/pravachan/README.md)** | transcripts, Hari Amrut, discourse catalogue |",
             f"| 💬 **[Paravani](text/paravani.md)** | {counts['paravani']} quotes |",
             f"| 📇 **[Parisishth](text/parisishth.md)** | {counts['parisishth']} glossary & bios |",
             f"| 🧭 **[Vicharan](text/vicharan.md)** | {counts['vicharan']} dated darshan |",
             f"| 🏷️ **[Themes](tags/README.md)** | browse by subject across {nthemes} themes |",
             "", "## Query", "",
             "**[`data/`](data/)** holds per-item JSON with structural + theme tags — one array "
             "per collection, plus [`tags.json`](data/tags.json) (the taxonomy). Every record "
             "carries `themes`, `type`, `source`, `lang`.", "",
             "## Tagging", "",
             "Every page has YAML frontmatter (Obsidian Properties): `type`, `work`, `section`, "
             "`themes`, `source`, and nested `tags` (`type/granth`, `granth/vachanamrut`, "
             "`theme/mahima`). Point an Obsidian vault at this folder to browse by tag and graph.", "",
             "## Sources & dedup", "",
             "See [`PROVENANCE.md`](PROVENANCE.md) — which source each work came from and how the "
             "four overlapping works were deduplicated (richer copy kept).", ""]
    write(OUT / "README.md", "\n".join(lines) + "\n")


def provenance(counts):
    lines = ["# Provenance & Deduplication", "",
             "Built by `tools/build_unified.py` from the two raw captures.", "",
             "## Overlaps resolved (richer copy kept)", "",
             "| Work | Kept from | Why |", "|---|---|---|",
             "| Swamini Vato | Paramrut app | adds Hindi, English, footnotes, topics |",
             "| Vachanamrut | Paramrut app | adds tithi, date, highlights |",
             "| Paravani (quotes) | merged | app `guru_raw` + website `date_en` |",
             "| Discourse catalogue | ihariprabodham.org | 2,263 vs the app's 581 |", "",
             "## Per collection", "", "| Collection | Records | Source |", "|---|---:|---|"]
    src = {"swamini-vato": "app", "vachanamrut": "app", "anirdeshi-amrut": "app",
           "shikshapatri": "app", "parisishth": "app", "paravani": "merged",
           "ambrish-upnishad": "web", "brahm-ratna": "web", "kirtan": "web",
           "prasang": "web", "pravachan-transcripts": "web", "hari-amrut": "web",
           "discourses": "web", "vicharan": "web"}
    for k in sorted(counts):
        lines.append(f"| {k} | {counts[k]} | {src.get(k,'?')} |")
    write(OUT / "PROVENANCE.md", "\n".join(lines) + "\n")


def main():
    counts = {}
    counts["swamini-vato"] = swamini_vato()
    counts["vachanamrut"] = vachanamrut()
    counts["anirdeshi-amrut"] = anirdeshi()
    counts["ambrish-upnishad"] = ambrish()
    counts["brahm-ratna"] = brahmratna()
    counts["shikshapatri"] = shikshapatri()
    counts["kirtan"] = kirtan()
    counts["prasang"] = prasang()
    counts["pravachan-transcripts"] = transcripts()
    counts["hari-amrut"] = hari_amrut()
    counts["discourses"] = catalogue()
    counts["paravani"] = paravani()
    counts["parisishth"] = parisishth()
    counts["vicharan"] = vicharan()
    (DATA).mkdir(parents=True, exist_ok=True)
    (DATA / "tags.json").write_text(json.dumps(list(TXMAP.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    nthemes = tag_pages()
    granth_readme(counts)
    pravachan_readme(counts)
    hub(counts, nthemes)
    provenance(counts)
    print("counts:", counts)
    print("total:", sum(counts.values()), "| themes:", nthemes,
          "| tagged items:", sum(len(v) for v in TAG_INDEX.values()))


if __name__ == "__main__":
    main()
