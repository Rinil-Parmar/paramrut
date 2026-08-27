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

### Rebuilding

```bash
tools/rebuild.sh              # regenerate data/ and text/   (~10s)
tools/rebuild.sh --source     # also re-mirror _source/ from the APK
python3 tools/build_nav.py    # rebuild indexes and tables of contents
```

| Path | What |
|---|---|
| [`tools/extract.py`](tools/extract.py) | asset bundle → `data/` + `text/` |
| [`tools/build_nav.py`](tools/build_nav.py) | index pages and per-file tables of contents |
| `_source/` | verbatim assets lifted from the app |
| `tools/paramrut-5.1.apk` | the app build everything came from |

---

## Provenance

Extracted from **Paramrut v5.1** (`org.hariprabodham.swaminivato`), published by HariPrabodham.

```
SHA-256  c14d44e77d8544306684a8b93c92e63afc2736c009b1b8075ab18dfcb9568f10
```

Audio and video are streamed by the app and are not part of the bundle, so they are not here.

## A note on use

This is devotional material belonging to the HariPrabodham sampraday and remains theirs. It is
organised here to make reading and study easier — the words are unchanged and no claim is made
over them. If you intend to build on it or redistribute it further, ask the sampraday first.
