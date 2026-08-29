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
def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def crumb():
    return "[← HariPrabodham corpus](../../README.md) · [Discourse catalogue](README.md)\n"


def links_cell(rec):
    out = []
    if rec.get("video"):
        out.append(f"[▶ Watch]({rec['video']})")
    if rec.get("audio"):
        a = rec["audio"]
        out.append(f"[♪ Audio]({a})" if a.startswith("http") else f"`{md_escape(a)}`")
    if rec.get("pdf"):
        out.append(f"[📄 PDF]({rec['pdf']})")
    return " · ".join(out) or "—"


def render_series(slug, title, desc, recs):
    by_year = {}
    for r in recs:
        by_year.setdefault(r["year"] or 0, []).append(r)
    lines = [crumb(), f"\n# {title}\n", f"*{desc}.*  \n**{len(recs)} discourses**, "
             f"{min(r['year'] for r in recs if r['year'])}–{max(r['year'] for r in recs if r['year'])}.\n"]
    # year jump bar
    years = sorted(by_year)
    lines.append("Jump to year: " + " · ".join(f"[{y}](#{y})" for y in years) + "\n")
    for y in years:
        rows = sorted(by_year[y], key=lambda r: (r["date"] or "", r["id"]))
        lines.append(f"\n## {y}\n")
        lines.append("| Date | Title | Topic | Place | Media |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            lines.append("| {date} | {title} | {topic} | {place} | {media} |".format(
                date=md_escape(r["date"] or ""),
                title=md_escape(r["title"] or ""),
                topic=md_escape(r["topic"] or ""),
                place=md_escape(r["place"] or ""),
                media=links_cell(r)))
    return "\n".join(lines) + "\n"


def render_vicharan(recs):
    by_year = {}
    for r in recs:
        by_year.setdefault(r["year"] or 0, []).append(r)
    years = sorted(by_year)
    lines = [crumb(), "\n# Vicharan\n",
             "*Dated darshan and vicharan of Guruhari Prabodhjivan Swamiji, with a Gujarati "
             f"description of each occasion.*  \n**{len(recs)} entries**, {min(years)}–{max(years)}.\n",
             "Jump to year: " + " · ".join(f"[{y}](#{y})" for y in years) + "\n"]
    for y in years:
        rows = sorted(by_year[y], key=lambda r: (r["date"] or "", r["id"]))
        lines.append(f"\n## {y}\n")
        lines.append("| Date | Place | Description | Video |")
        lines.append("|---|---|---|---|")
        for r in rows:
            vid = f"[▶ Watch]({r['video']})" if r.get("video") else "—"
            lines.append("| {d} | {p} | {desc} | {v} |".format(
                d=md_escape(r["date"] or ""), p=md_escape(r["place"] or ""),
                desc=md_escape(r["description"] or ""), v=vid))
    return "\n".join(lines) + "\n"


def render_pravachan(recs):
    lines = [crumb(), "\n# Audio Pravachan\n",
             "*Audio pravachan of Guruhari Prabodhjivan Swamiji, streamed by the app.*  \n"
             f"**{len(recs)} recordings.**\n",
             "| Date | Title | Album | Note | Audio |", "|---|---|---|---|---|"]
    for r in sorted(recs, key=lambda r: (r["date"] or "", r["id"])):
        aud = f"[♪ Listen]({r['audio']})" if r.get("audio") else "—"
        lines.append("| {d} | {t} | {a} | {n} | {au} |".format(
            d=md_escape(r["date"] or ""), t=md_escape(r["title"] or ""),
            a=md_escape(r["album"] or ""), n=md_escape(r["text"] or ""), au=aud))
    return "\n".join(lines) + "\n"


def render_hindi(recs):
    lines = [crumb(), "\n# Hindi Paravani\n",
             "*Hindi paravani booklets of Swamishri, as PDF.*  \n"
             f"**{len(recs)} booklets.**\n",
             "| Title | PDF |", "|---|---|"]
    for r in sorted(recs, key=lambda r: r["id"]):
        pdf = f"[📄 Open]({r['pdf']})" if r.get("pdf") else "—"
        lines.append(f"| {md_escape(r['title'] or '')} | {pdf} |")
    return "\n".join(lines) + "\n"


def render_index(counts):
    total = sum(counts.values())
    lines = ["[← HariPrabodham corpus](../../README.md)\n", "\n# Discourse & Darshan Catalogue\n",
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

    raw, counts, digests = {}, {}, {}
    for name in ("hariparamrut", "aksharvani", "santvani", "vicharan", "pravachan", "hindipravachan"):
        blob = fetch(name)
        (src / f"{name}.json").write_bytes(blob)
        digests[name] = hashlib.sha256(blob).hexdigest()
        raw[name] = json.loads(blob.decode("utf-8-sig"))
        counts[name] = len(raw[name])
        print(f"  {name:16s} {counts[name]:4d} records  sha256={digests[name][:12]}…")

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
