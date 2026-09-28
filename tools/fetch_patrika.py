#!/usr/bin/env python3
"""Fetch every HariPrabodham Patrika PDF into the repo.

The Patrika app (com.hari.patrika.patrika) serves its catalogue from Cloud Firestore
(project patrika-b00e1); the PDFs themselves are public Azure blobs. This reads only the
app's own public content collections (never user/auth data) and downloads the exact PDF
URLs they list — no URL guessing.

    python3 tools/fetch_patrika.py            # fetch all categories
    python3 tools/fetch_patrika.py --list     # just print the catalogue, download nothing
    python3 tools/fetch_patrika.py akshardhara prasang   # subset

Categories map to Firestore collections; unknown ones are probed from a fixed
content-collection candidate list and skipped if empty. Audio pravachan is ignored.
"""
import argparse, hashlib, json, re, sys, urllib.request, urllib.parse
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDFDIR = ROOT / "pdf"
DATADIR = ROOT / "data" / "patrika"
TEXTDIR = ROOT / "text" / "patrika"

PROJECT = "patrika-b00e1"
KEY = "AIzaSyCB-tU4wo45DtB_PCjLIThaj91ESB6W_lc"   # app's embedded public web API key
FS = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
UA = {"User-Agent": "Dart/3.5 (dart:io)"}

# category -> (candidate collection names, field map). First non-empty collection wins.
CATEGORIES = {
    "akshardhara":   (["IssueMaster"],                 {"id": "IssueId", "date": "IssueDate",
                       "pdf": "IssuePdf", "title": "IssueDetail", "del": "IsDelete"}),
    "prasang":       (["Prasang"],                     {"id": "prasangId", "date": "prasangDate",
                       "pdf": "fileUrl", "title": "title", "subject": "subject",
                       "detail": "detail", "del": "isDeleted"}),
    "paravani":      (["Paravani", "ParavaniMaster"],  {"id": "ParavaniId", "date": "ParavaniDate",
                       "pdf": "ParavaniPdf", "title": "ParavaniDetail", "del": "IsDelete"}),
    "vicharan":      (["Vicharan", "VicharanMaster", "Report", "ReportMaster"],
                      {"id": "id", "date": "date", "pdf": "fileUrl", "title": "title", "del": "isDeleted"}),
    "hindi-paravani": (["HindiParavani", "HindiParavaniMaster"],
                      {"id": "id", "date": "date", "pdf": "fileUrl", "title": "title", "del": "isDeleted"}),
}


def sval(v):
    """Unwrap a Firestore typed value."""
    if not isinstance(v, dict):
        return v
    (t, x), = v.items()
    if t == "integerValue":
        return int(x)
    if t == "booleanValue":
        return bool(x)
    return x


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()


def collection(name):
    """All docs of a Firestore collection via REST, paginated. [] if empty/missing."""
    out, tok = [], None
    while True:
        u = f"{FS}/{name}?key={KEY}&pageSize=300" + (f"&pageToken={tok}" if tok else "")
        try:
            j = json.loads(get(u))
        except urllib.error.HTTPError as e:
            print(f"    {name}: HTTP {e.code}"); return out
        for d in j.get("documents", []):
            out.append({k: sval(v) for k, v in d.get("fields", {}).items()})
        tok = j.get("nextPageToken")
        if not tok:
            return out


def resolve(cands):
    for c in cands:
        docs = collection(c)
        if docs:
            return c, docs
    return None, []


def clean_pdf_url(u):
    if not u:
        return None
    u = str(u).strip().replace("\\/", "/")
    if not u.lower().endswith(".pdf") or "example" in u:
        return None
    return u.replace("http://", "https://")


def fname(cat, rec, fm, url):
    d = rec.get(fm["date"])
    dt = None
    if d:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", str(d))
        dt = m.group(1) if m else None
    if cat == "akshardhara":                       # one issue per month → date is unique
        stem = dt or f"{cat}-{rec.get(fm['id'], 'x')}"
    else:                                           # multiple per date → use source filename (unique)
        base = urllib.parse.unquote(url.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
        base = re.sub(r"[^0-9A-Za-z._-]", "_", base) or f"{cat}-{rec.get(fm['id'], 'x')}"
        stem = f"{dt}-{base}" if dt else base
    return dt, f"{stem}.pdf"


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = get(url)
    if not data[:5].startswith(b"%PDF"):
        return None, "not-a-pdf"
    dest.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cats", nargs="*", help="subset of: " + ", ".join(CATEGORIES))
    ap.add_argument("--list", action="store_true", help="print catalogue, download nothing")
    args = ap.parse_args()
    cats = args.cats or list(CATEGORIES)

    DATADIR.mkdir(parents=True, exist_ok=True)
    manifest = {"source": {"project": PROJECT, "firestore": FS, "fetched": date.today().isoformat()},
                "collections": {}}
    grand = 0
    for cat in cats:
        cands, fm = CATEGORIES[cat]
        col, docs = resolve(cands)
        if not docs:
            print(f"{cat}: no collection found (tried {cands})"); continue
        live = [d for d in docs if not d.get(fm.get("del"), False)]
        rows = []
        for r in sorted(live, key=lambda r: str(r.get(fm["date"]) or "")):
            url = clean_pdf_url(r.get(fm["pdf"]))
            if not url:
                continue
            dt, fn = fname(cat, r, fm, url)
            year = (dt or "")[:4] or "undated"
            relpath = f"pdf/{cat}/{year}/{fn}" if cat in ("paravani",) else f"pdf/{cat}/{fn}"
            rec = {"id": r.get(fm["id"]), "date": dt, "title": r.get(fm.get("title")),
                   "pdf_url": url, "path": relpath}
            if fm.get("subject"):
                rec["subject"] = r.get(fm["subject"])
            if fm.get("detail"):
                rec["detail"] = r.get(fm["detail"])
            rows.append(rec)
        print(f"{cat}: collection={col} total={len(docs)} live={len(live)} with-pdf={len(rows)}")
        if not args.list:
            for rec in rows:
                dest = ROOT / rec["path"]
                if dest.exists():
                    rec["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
                    continue
                try:
                    sha, size = download(rec["pdf_url"], dest)
                    if sha:
                        rec["sha256"] = sha
                        print(f"    ✓ {rec['path']} ({size//1024} KB)")
                    else:
                        print(f"    ✗ {rec['path']}: {size}")
                except Exception as e:
                    print(f"    ✗ {rec['pdf_url']}: {type(e).__name__}")
        (DATADIR / f"{cat}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest["collections"][cat] = {"collection": col, "total": len(docs),
                                        "live": len(live), "pdfs": len(rows)}
        grand += len(rows)
    manifest["total_pdfs"] = grand
    (DATADIR / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ntotal PDFs catalogued: {grand}")
    if not args.list:
        build_readme(manifest)


def build_readme(manifest):
    TEXTDIR.mkdir(parents=True, exist_ok=True)
    lines = ["# HariPrabodham Patrika", "",
             "PDF archive of the HariPrabodham Patrika publications, fetched from the app's "
             "public catalogue. Each links to the local PDF in this repo.", "",
             f"_Fetched {manifest['source']['fetched']} · {manifest.get('total_pdfs', 0)} PDFs._", ""]
    titles = {"akshardhara": "Akshardhara", "paravani": "Paravani", "prasang": "Prasang",
              "vicharan": "Vicharan", "hindi-paravani": "Hindi Paravani"}
    for cat, meta in manifest["collections"].items():
        rows = json.loads((DATADIR / f"{cat}.json").read_text())
        if not rows:
            continue
        lines += [f"## {titles.get(cat, cat)} ({len(rows)})", ""]
        by_year = {}
        for r in rows:
            by_year.setdefault((r["date"] or "")[:4] or "undated", []).append(r)
        for yr in sorted(by_year, reverse=True):
            if len(by_year) > 1:
                lines += [f"### {yr}", ""]
            lines += ["| Date | Title | PDF |", "|---|---|---|"]
            for r in sorted(by_year[yr], key=lambda r: r["date"] or ""):
                t = (r.get("title") or r.get("subject") or "").replace("|", "\\|")
                rel = "../../" + r["path"]
                lines.append(f"| {r['date'] or ''} | {t} | [PDF]({rel}) |")
            lines += [""]
    (TEXTDIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"→ {TEXTDIR/'README.md'}")


if __name__ == "__main__":
    main()
