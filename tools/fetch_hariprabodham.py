#!/usr/bin/env python3
"""Fetch the HariPrabodham discourse & darshan catalogue and render it.

The HariPrabodham app family (com.hari.patrika.patrika and the paramrut app) reads
its discourse index live from a shared PHP backend, `dbphp.prabodhswamiji.in`.
Unlike the Paramrut scriptures — which ship inside the app bundle — this content is
a *catalogue*: each record is a dated sabha or vicharan with a place, an optional
topic line, and links out to YouTube, audio and PDF. There is no long-form body to
extract; what is captured here is the full, structured index of every discourse the
app lists, with its media links intact.

Six endpoints are read:

    hariparamrut.php   Hari Paramrut     video series   (date, place, YouTube, audio)
    aksharvani.php     Akshar Vani       video series
    santvani.php       Sant Vani         video series
    vicharan.php       Vicharan          dated darshan  (+ Gujarati descriptions)
    pravachan.php      Audio Pravachan   Azure-hosted mp3
    hindipravachan.php Hindi Paravani    PDF booklets

Writes, mirroring the Paramrut layout:
    _source/hariprabodham/*.json   verbatim server responses (provenance)
    data/hariprabodham/*.json      cleaned, flat arrays
    text/hariprabodham/*.md        readable catalogues, grouped by year
    text/hariprabodham/README.md   the collection index

Nothing is invented. The only edits are: repairing double-encoded (cp1252/UTF-8)
mojibake in the topic lines, flattening the nested Vicharan date object to its date
string, and un-escaping URL backslashes. Numeric speaker/category codes are kept
as-is — the backend exposes no lookup for them.
"""

import json, re, sys, hashlib, urllib.request, unicodedata
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://dbphp.prabodhswamiji.in/"
UA   = "Dart/3.5 (dart:io)"
THUMB_HOST = "http://thumbnail.prabodhswamiji.in/"

# endpoint -> (slug, display title, one-line description)
SERIES = {
    "hariparamrut":   ("hari-paramrut",   "Hari Paramrut",   "Discourses of Guruhari Prabodhjivan Swamiji"),
    "aksharvani":     ("akshar-vani",     "Akshar Vani",     "Akshar Vani discourse series"),
    "santvani":       ("sant-vani",       "Sant Vani",       "Sant Vani discourse series"),
}


# ── fetch ────────────────────────────────────────────────────────────────────
def fetch(name):
    req = urllib.request.Request(BASE + name + ".php", headers={"User-Agent": UA, "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=60).read()


# ── cleaning helpers ─────────────────────────────────────────────────────────
def demojibake(s):
    """Repair text double-encoded as UTF-8-through-cp1252 (â€“ -> –).

    Only touched when the tell-tale bytes are present and the round-trip succeeds;
    clean Gujarati and plain ASCII are returned unchanged."""
    if not s:
        return s
    if any(x in s for x in ("Ã", "â€", "Â", "â€™", "â€“")):
        try:
            return s.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def norm(s):
    if s is None:
        return None
    s = demojibake(str(s)).replace("\r\n", "\n").strip()
    s = re.sub(r"[ \t]+", " ", s)
    return s or None


def url(s):
    if not s:
        return None
    return norm(str(s).replace("\\/", "/"))


def flat_date(v):
    """Vicharan dates arrive as {'date': 'YYYY-MM-DD HH:MM:SS...', ...}."""
    if isinstance(v, dict):
        v = v.get("date", "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(v))
    return m.group(1) if m else (str(v).strip() or None)


def audio_link(fn):
    """Audio values in the video series are bare filenames; pravachan already
    carries a full Azure URL. Return a full URL when we have one, else the
    filename verbatim (the app resolves it against a host not exposed publicly)."""
    if not fn:
        return None
    fn = url(fn)
    return fn if fn and fn.startswith("http") else fn


# ── record normalisers ───────────────────────────────────────────────────────
def clean_series(r):
    """hariparamrut / aksharvani / santvani share one schema."""
    return {
        "id":       int(r["InfoId"]),
        "title":    norm(r.get("Title")),
        "date":     flat_date(r.get("InfoDate")),
        "year":     int(r["InfoYear"]) if str(r.get("InfoYear", "")).strip() else None,
        "place":    norm(r.get("Place")),
        "city":     norm(r.get("City")),
        "pradesh":  norm(r.get("Pradesh")),
        "topic":    norm(r.get("SabhaDetail")),
        "video":    url(r.get("VideoUrl")),
        "thumb":    url(r.get("VideoThumb")),
        "audio":    audio_link(r.get("audio")),
        "speaker_code": int(r["Vakta"]) if str(r.get("Vakta", "")).strip() else None,
    }


def clean_vicharan(r):
    return {
        "id":       int(r["infoid"]),
        "date":     flat_date(r.get("infodate")),
        "year":     int(r["infoyear"]) if str(r.get("infoyear", "")).strip() else None,
        "place":    norm(r.get("place")),
        "description": norm(r.get("shortdescguj")),
        "video":    url(r.get("videourl")),
    }


def clean_pravachan(r):
    return {
        "id":      int(r["pid"]),
        "title":   norm(r.get("title")),
        "date":    flat_date(r.get("pdate")),
        "year":    int(r["year"]) if str(r.get("year", "")).strip() else None,
        "album":   norm(r.get("album")),
        "text":    norm(r.get("text")),
        "audio":   url(r.get("audio")),
        "image":   url(r.get("img")),
    }


def clean_hindi(r):
    return {
        "id":     int(r["pid"]),
        "title":  norm(r.get("title")),
        "pdf":    url(r.get("pdf")),
        "image":  url(r.get("img")),
        "category": norm(r.get("category")),
    }


# ── markdown rendering ───────────────────────────────────────────────────────
# Paramrut-style reading pages: breadcrumb, H1, a collapsible Contents index, then
# every discourse as its own `## ` heading with italic metadata, body and links —
# so the file reads top-to-bottom and the GitHub outline sidebar works.
MARK = "<!-- nav:generated -->"
CRUMB = "[← Paramrut](../../README.md) · [Reading the corpus](../README.md) · [Discourse catalogue](README.md)"


def gh_anchor(text, seen):
    """GitHub heading-anchor slug, matching build_nav.py (keeps Gujarati matras)."""
    out = []
    for ch in text.strip().lower():
        if ch == " ":
            out.append("-")
        elif ch in "-_" or unicodedata.category(ch)[0] in ("L", "N", "M"):
            out.append(ch)
    a = "".join(out)
    n = seen[a]; seen[a] += 1
    return a if n == 0 else f"{a}-{n}"


def clean_title(t):
    """Underscore-joined titles from the DB → readable ('Akshar_Vani_1' → 'Akshar Vani 1')."""
    if not t:
        return t
    return re.sub(r"\s+", " ", t.replace("_", " ")).strip()


def media_line(rec):
    out = []
    if rec.get("video"):
        out.append(f"▶ [Watch on YouTube]({rec['video']})")
    if rec.get("audio"):
        a = rec["audio"]
        out.append(f"♪ [Audio]({a})" if a.startswith("http") else f"♪ Audio: `{a}`")
    if rec.get("pdf"):
        out.append(f"📄 [Open PDF]({rec['pdf']})")
    return "  ·  ".join(out)


def build_page(title, subtitle, entries):
    """entries: list of (heading_text, [body_line, ...]).  Emits a full page with a
    collapsible table of contents and one `## ` section per entry."""
    import collections
    seen = collections.defaultdict(int)
    toc, body = [], []
    for heading, lines in entries:
        anchor = gh_anchor(heading, seen)
        toc.append(f"- [{heading}](#{anchor})")
        body.append(f"\n## {heading}\n")
        body.extend(lines)
        body.append("\n---")
    open_by_default = len(entries) <= 25
    out = [CRUMB, "", f"# {title}", "", subtitle, "", MARK, "",
           f'<details{" open" if open_by_default else ""}>',
           f"<summary><b>Contents</b> — {len(entries)} entries</summary>", "",
           *toc, "", "</details>", "", "---", *body, ""]
    return "\n".join(out)


def render_series(slug, title, desc, recs):
    recs = sorted(recs, key=lambda r: (r["date"] or "", r["id"]))
    yrs = [r["year"] for r in recs if r["year"]]
    subtitle = f"*{desc}.*  \n**{len(recs)} discourses** · {min(yrs)}–{max(yrs)}."
    entries = []
    for r in recs:
        head = " · ".join(x for x in [r["date"], clean_title(r["title"])] if x) or f"#{r['id']}"
        loc = ", ".join(x for x in [r["place"], r["city"]] if x)
        meta = " · ".join(x for x in [loc, r["pradesh"]] if x)
        lines = []
        if meta:
            lines += [f"_{meta}_", ""]
        if r.get("topic"):
            lines += [r["topic"], ""]
        ml = media_line(r)
        if ml:
            lines += [ml]
        entries.append((head, lines))
    return build_page(title, subtitle, entries)


def render_vicharan(recs):
    recs = sorted(recs, key=lambda r: (r["date"] or "", r["id"]))
    yrs = [r["year"] for r in recs if r["year"]]
    subtitle = ("*Dated darshan and vicharan of Guruhari Prabodhjivan Swamiji, with a Gujarati "
                f"description of each occasion.*  \n**{len(recs)} entries** · {min(yrs)}–{max(yrs)}.")
    entries = []
    for r in recs:
        head = " · ".join(x for x in [r["date"], r["place"]] if x) or f"#{r['id']}"
        lines = []
        if r.get("description"):
            lines += [r["description"], ""]
        ml = media_line(r)
        if ml:
            lines += [ml]
        entries.append((head, lines))
    return build_page("Vicharan", subtitle, entries)


def render_pravachan(recs):
    recs = sorted(recs, key=lambda r: (r["date"] or "", r["id"]))
    subtitle = ("*Audio pravachan of Guruhari Prabodhjivan Swamiji, streamed by the app.*  \n"
                f"**{len(recs)} recordings.**")
    entries = []
    for r in recs:
        head = " · ".join(x for x in [r["date"], clean_title(r["title"])] if x) or f"#{r['id']}"
        lines = []
        sub = " · ".join(x for x in [r["album"], r["text"]] if x)
        if sub:
            lines += [f"_{sub}_", ""]
        ml = media_line(r)
        if ml:
            lines += [ml]
        entries.append((head, lines))
    return build_page("Audio Pravachan", subtitle, entries)


def render_hindi(recs):
    recs = sorted(recs, key=lambda r: r["id"])
    subtitle = ("*Hindi paravani booklets of Swamishri, as PDF.*  \n"
                f"**{len(recs)} booklets.**")
    entries = []
    for r in recs:
        head = clean_title(r["title"]) or f"#{r['id']}"
        lines = []
        ml = media_line(r)
        if ml:
            lines += [ml]
        entries.append((head, lines))
    return build_page("Hindi Paravani", subtitle, entries)


def render_index(counts):
    total = sum(counts.values())
    lines = ["[← Paramrut](../../README.md) · [Reading the corpus](../README.md)\n",
             "\n# Discourse & Darshan Catalogue\n",
             "A structured index of the discourses, darshan and audio that the "
             "[HariPrabodham app](https://play.google.com/store/apps/details?id=com.hari.patrika.patrika) "
             "lists — dates, places, speakers and direct links to watch or listen.  \n"
             f"**{total} records** across six series. The talks themselves stay on YouTube and the "
             "sampraday's servers; what is captured here is the full catalogue and its links.\n",
             "## Series\n",
             "| | Series | Records | Contents |",
             "|---|---|---:|---|",
             f"| 🎙️ | **[Hari Paramrut](hari-paramrut.md)** | {counts['hariparamrut']} | Video · date · place · audio |",
             f"| 🔆 | **[Akshar Vani](akshar-vani.md)** | {counts['aksharvani']} | Video · date · place · audio |",
             f"| 🌼 | **[Sant Vani](sant-vani.md)** | {counts['santvani']} | Video · date · place · audio |",
             f"| 🧭 | **[Vicharan](vicharan.md)** | {counts['vicharan']} | Dated darshan · Gujarati description · video |",
             f"| 🎧 | **[Audio Pravachan](audio-pravachan.md)** | {counts['pravachan']} | Azure-hosted audio |",
             f"| 📄 | **[Hindi Paravani](hindi-paravani.md)** | {counts['hindipravachan']} | PDF booklets |",
             "\n## What this is\n",
             "This is a **catalogue**, not a text corpus. The HariPrabodham app reads this index "
             "live from a shared backend (`dbphp.prabodhswamiji.in`); each record points at a "
             "discourse hosted on YouTube, an audio file, or a PDF. Every field the backend "
             "returns is preserved here — dates, places, pradesh, topic lines and media links — "
             "so the whole listing is readable and searchable offline, and every talk is one "
             "click away.\n",
             "The same records are in [`data/hariprabodham/`](../../data/hariprabodham/) as JSON.\n"]
    return "\n".join(lines) + "\n"


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    src  = ROOT / "_source" / "hariprabodham"
    data = ROOT / "data" / "hariprabodham"
    text = ROOT / "text" / "hariprabodham"
    for p in (src, data, text):
        p.mkdir(parents=True, exist_ok=True)

    # By default re-render from the verbatim responses already in _source/ (stable
    # provenance, no network). Pass --refetch to pull fresh from the backend.
    refetch = "--refetch" in sys.argv
    raw, counts, digests = {}, {}, {}
    for name in ("hariparamrut", "aksharvani", "santvani", "vicharan", "pravachan", "hindipravachan"):
        cached = src / f"{name}.json"
        if refetch or not cached.exists():
            blob = fetch(name)
            cached.write_bytes(blob)
            tag = "fetched"
        else:
            blob = cached.read_bytes()
            tag = "cached "
        digests[name] = hashlib.sha256(blob).hexdigest()
        raw[name] = json.loads(blob.decode("utf-8-sig"))
        counts[name] = len(raw[name])
        print(f"  {tag} {name:16s} {counts[name]:4d} records  sha256={digests[name][:12]}…")

    def dump(slug, recs):
        (data / f"{slug}.json").write_text(
            json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")

    # series
    for ep, (slug, title, desc) in SERIES.items():
        recs = [clean_series(r) for r in raw[ep]]
        dump(slug, recs)
        (text / f"{slug}.md").write_text(render_series(slug, title, desc, recs), encoding="utf-8")

    vic = [clean_vicharan(r) for r in raw["vicharan"]]
    dump("vicharan", vic)
    (text / "vicharan.md").write_text(render_vicharan(vic), encoding="utf-8")

    prv = [clean_pravachan(r) for r in raw["pravachan"]]
    dump("audio-pravachan", prv)
    (text / "audio-pravachan.md").write_text(render_pravachan(prv), encoding="utf-8")

    hin = [clean_hindi(r) for r in raw["hindipravachan"]]
    dump("hindi-paravani", hin)
    (text / "hindi-paravani.md").write_text(render_hindi(hin), encoding="utf-8")

    (text / "README.md").write_text(render_index(counts), encoding="utf-8")

    manifest = {
        "source": {
            "backend": BASE,
            "apps": ["com.hari.patrika.patrika", "org.hariprabodham.swaminivato"],
            "publisher": "HariPrabodham",
            "fetched": date.today().isoformat(),
        },
        "endpoints": {
            name: {"records": counts[name], "sha256": digests[name]}
            for name in counts
        },
        "total_records": sum(counts.values()),
    }
    (data / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  total {sum(counts.values())} records → data/hariprabodham/ + text/hariprabodham/")


if __name__ == "__main__":
    main()
