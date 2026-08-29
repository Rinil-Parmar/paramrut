# Paramrut

**The scripture corpus of the HariPrabodham sampraday — 1,024,137 words, structured and readable.**

Swamini Vato, the Vachanamrut, Anirdeshi Amrut, the Shikshapatri and more, extracted from the
[Paramrut app](https://play.google.com/store/apps/details?id=org.hariprabodham.swaminivato) and rewritten into
clean Markdown you can read in the browser and JSON you can query.

The text is unchanged. What has been added is structure: the app's private markup resolved into
real headings, footnotes, verse and emphasis — and an index in front of every page.

---

## Read

| | Collection | Contents | Languages |
|---|---|---|---|
| 📖 | **[Swamini Vato](text/swamini-vato/README.md)** | 3,825 vato · 16 prakarans | ગુજરાતી · हिन्दी · English |
| 🪔 | **[Vachanamrut](text/vachanamrut/README.md)** | 274 vachanamrut · 12 sections | ગુજરાતી |
| 🌸 | **[Anirdeshi Amrut](text/anirdeshi-amrut/README.md)** | 1,549 sabha · 3 kalash | ગુજરાતી |
| 📜 | **[Shikshapatri](text/shikshapatri.md)** | 212 shlokas | संस्कृत · ગુજરાતી · हिन्दी |
| 💬 | **[Guruhari Paravani](text/quotes.md)** | 541 quotes | ગુજરાતી |
| 📇 | **[Parisishth](text/parisishth.md)** | 83 entries · glossary & biographies | ગુજરાતી |
| 🙏 | **[Ashirvad](text/ashirvad.md)** | 1 | ગુજરાતી |

Start at **[text/](text/README.md)** for the full reading index. Every page opens with its own
table of contents, so you can jump straight to a vato or a vachanamrut.

## Watch & listen

Alongside the scriptures, the repository carries the **[HariPrabodham discourse & darshan
catalogue](text/hariprabodham/README.md)** — a structured index of **581 discourses** (Hari
Paramrut, Akshar Vani, Sant Vani, Vicharan and audio pravachan) with dates, places, speakers and
direct links to watch or listen. This is a *catalogue*, not a text corpus: the talks live on
YouTube and the sampraday's servers; captured here is the full listing and every link, read live
from the app's backend.

| | Series | Records | Contents |
|---|---|---:|---|
| 🎙️ | **[Hari Paramrut](text/hariprabodham/hari-paramrut.md)** | 109 | video · date · place · audio |
| 🔆 | **[Akshar Vani](text/hariprabodham/akshar-vani.md)** | 102 | video · date · place · audio |
| 🌼 | **[Sant Vani](text/hariprabodham/sant-vani.md)** | 67 | video · date · place · audio |
| 🧭 | **[Vicharan](text/hariprabodham/vicharan.md)** | 295 | dated darshan · Gujarati description · video |
| 🎧 | **[Audio Pravachan](text/hariprabodham/audio-pravachan.md)** | 6 | Azure-hosted audio |
| 📄 | **[Hindi Paravani](text/hariprabodham/hindi-paravani.md)** | 2 | PDF booklets |

## Query

**[data/](data/README.md)** holds the same corpus as UTF-8 JSON — one flat array per collection.

| File | Records |
|---|---:|
| [`swamini-vato.json`](data/swamini-vato.json) | 3,825 |
| [`vachanamrut.json`](data/vachanamrut.json) | 274 |
| [`anirdeshi-amrut.json`](data/anirdeshi-amrut.json) | 1,549 |
| [`shikshapatri.json`](data/shikshapatri.json) | 212 |
| [`quotes.json`](data/quotes.json) | 541 |
| [`parisishth.json`](data/parisishth.json) | 83 |
| [`topics.json`](data/topics.json) | 33 themes |

The discourse catalogue is in **[`data/hariprabodham/`](data/hariprabodham/)** — six JSON arrays
(581 records) plus an `index.json` manifest with fetch date and per-endpoint checksums.

Field-by-field documentation is in **[data/README.md](data/README.md)**.

---

## What's in the corpus

### Swamini Vato

3,825 vato across 16 prakarans. Gujarati is **complete** — 3,825 of
3,825, none missing. Hindi covers prakaran 1–8 (1,547 vato) and English covers
prakaran 1 (343); those are the limits of the source app, not of the extraction.

Carried through with the text: **1,517 Gujarati footnote glosses**, rendered as a **Notes**
list beneath each vato, and the cross-references into the Vachanamrut.

A thematic index of **33 subjects** ([`topics.json`](data/topics.json)) maps themes onto
vato ids, for reading by subject rather than in order.

### Vachanamrut

All 274 vachanamrut, each with its tithi, Gregorian date and weekday.

| Section | Count |
|---|---:|
| Gadhada Pratham | 78 |
| Sarangpur | 18 |
| Kariyani | 12 |
| Loya | 18 |
| Panchala | 7 |
| Gadhada Madhya | 67 |
| Vartal | 20 |
| Amadavad | 8 |
| Gadhada Antya | 39 |
| Jetalpur | 5 |
| Kariyani (misc) | 1 |
| Ashirvad | 1 |

The **293 passages the app marks as key teachings** are preserved — bold in the Markdown,
and a `highlights` array on each JSON record.

### Anirdeshi Amrut

1,549 dated sabha of Guruhari Hariprasad Swamishri, in 3 kalash and
13 achaman, each carrying the source's own subject tags.

### Shikshapatri, quotes and glossary

The 212 shlokas of the Shikshapatri in Sanskrit with Gujarati and Hindi
(55 marked as selected in the source); 541 quotes of
Guruhari Hariprasad Swamishri and Guruhari Prabodhjivan Swamiji; and 83
Parisishth entries of glossary and biography.

---

## How it was made

The Paramrut app is a Flutter app that ships its entire library **offline, unencrypted**, as JSON,
HTML and text assets. Nothing was fetched from a server and nothing was decrypted — the files were
read out of the app bundle, the app's own markup was resolved, and the result was rewritten.

The source text uses a small private markup, all of it decoded here:

| Marker | Meaning | Becomes |
|---|---|---|
| `$` | paragraph break | blank line |
| `${Title}…$` | title of the passage | heading / `title_gu` |
| `${Slok}` | verse line | blockquote |
| `#ex1WORD /#ex1` | inline glossary term | the plain word, gloss moved to `footnotes` |
| `@` | separates body from its numbered gloss block | a **Notes** list |
| `*#…#*` | passage the app highlights | **bold**, plus a `highlights` entry |

`||` is a genuine Sanskrit danda and is left as-is.

Two normalisations were applied to inconsistent source fields, both reversible:

- **Guru attribution** on the quotes collapsed from 33 spelling variants to two canonical names.
  The original string is kept in `guru_raw`. Nine quotes carry no attribution anywhere and are `null`.
- **`કળશ ૧`**, a single typo'd record, was folded into `કળશ - ૧`.

Nothing else was edited, reworded or summarised.

### The discourse catalogue

The [HariPrabodham catalogue](text/hariprabodham/README.md) comes from a different place. Its
records are **not** in any app bundle — the app reads them live from a shared PHP backend,
`dbphp.prabodhswamiji.in`, over six open (unauthenticated) endpoints. Those responses are fetched
verbatim into [`_source/hariprabodham/`](_source/hariprabodham/), then cleaned into JSON and
readable Markdown. The only edits are: repairing double-encoded (cp1252/UTF-8) mojibake in the
topic lines, flattening the Vicharan date object to its date string, and un-escaping URL
backslashes. Numeric speaker/category codes are kept as-is — the backend exposes no lookup for
them. The audio, video and PDF stay where they are; only their links are recorded.

### Rebuilding

```bash
tools/rebuild.sh              # regenerate data/ and text/   (~10s)
tools/rebuild.sh --source     # also re-mirror _source/ from the APK
python3 tools/build_nav.py    # rebuild indexes and tables of contents
python3 tools/fetch_hariprabodham.py   # re-fetch the discourse catalogue from the backend
```

| Path | What |
|---|---|
| [`tools/extract.py`](tools/extract.py) | asset bundle → `data/` + `text/` |
| [`tools/build_nav.py`](tools/build_nav.py) | index pages and per-file tables of contents |
| [`tools/fetch_hariprabodham.py`](tools/fetch_hariprabodham.py) | discourse backend → `data/hariprabodham/` + `text/hariprabodham/` |
| `_source/` | verbatim assets lifted from the app, and verbatim backend responses |
| `tools/paramrut-5.1.apk` | the app build the scriptures came from |

---

## Provenance

Extracted from **Paramrut v5.1** (`org.hariprabodham.swaminivato`), published by HariPrabodham.

```
SHA-256  c14d44e77d8544306684a8b93c92e63afc2736c009b1b8075ab18dfcb9568f10
```

Audio and video are streamed by the app and are not part of the bundle, so they are not here.

The discourse catalogue was read from the HariPrabodham backend `dbphp.prabodhswamiji.in`
(shared by `com.hari.patrika.patrika` and `org.hariprabodham.swaminivato`) on 2026-08-29.
Per-endpoint record counts and SHA-256 checksums of the raw responses are in
[`data/hariprabodham/index.json`](data/hariprabodham/index.json).

## A note on use

This is devotional material belonging to the HariPrabodham sampraday and remains theirs. It is
organised here to make reading and study easier — the words are unchanged and no claim is made
over them. If you intend to build on it or redistribute it further, ask the sampraday first.
