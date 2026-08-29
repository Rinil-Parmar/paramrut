[← Repository](../../README.md)

# iHariPrabodham

**The textual corpus published by [ihariprabodham.org](https://www.ihariprabodham.org) — scripture, prasang, kirtan and discourse, structured and readable.**

The website streams its content from public data files and APIs. Every **textual** source is
captured here — the words, their descriptions and their links — and rewritten into clean Markdown
you can read in the browser and JSON you can query. Images, audio and video are not copied; only
their links are kept.

The text is unchanged. What is added is structure: the app's private markup resolved into real
headings, footnotes and verse, and an index in front of every page.

---

## Read

| | Collection | Contents | |
|---|---|---|---|
| 📖 | **[Swamini Vato](swamini-vato/README.md)** | 3,825 vato · 16 prakaran | ગુજરાતી |
| 🪔 | **[Vachanamrut](vachanamrut/README.md)** | 274 vachanamrut · 12 sections | ગુજરાતી |
| 📿 | **[Prasang](prasang/README.md)** | 965 incident-stories · 54 themes | ગુજરાતી |
| 🎼 | **[Kirtan](kirtan/README.md)** | 514 kirtan · shlok · aarti | ગુજરાતી |
| 🗣️ | **[Pravachan Transcripts](pravachan/README.md)** | 232 daily discourses · 7 years | ગુજરાતી |
| 💬 | **[Guruhari Paravani](quotes.md)** | 541 quotes | ગુજરાતી |
| 🧭 | **[Vicharan](vicharan.md)** | 295 dated darshan | ગુજરાતી |
| 📝 | **[Pravachan Notes](pravachan-notes.md)** | 246 subject / prasang / reference notes | ગુજરાતી |
| 🎥 | **[Discourse Catalogue](discourses/README.md)** | 2,263 discourses · 28 series | text + YouTube links |

Every page opens with its own table of contents, so you can jump straight to a vato, a prasang or
a transcript.

## Query

**[`data/ihariprabodham/`](../../data/ihariprabodham/)** holds the same corpus as UTF-8 JSON — one
flat array per collection, plus an `index.json` manifest.

| File | Records |
|---|---:|
| [`swamini-vato.json`](../../data/ihariprabodham/swamini-vato.json) | 3,825 |
| [`vachanamrut.json`](../../data/ihariprabodham/vachanamrut.json) | 274 |
| [`prasang.json`](../../data/ihariprabodham/prasang.json) | 965 |
| [`kirtan.json`](../../data/ihariprabodham/kirtan.json) | 514 |
| [`pravachan-transcripts.json`](../../data/ihariprabodham/pravachan-transcripts.json) | 232 |
| [`quotes.json`](../../data/ihariprabodham/quotes.json) | 541 |
| [`vicharan.json`](../../data/ihariprabodham/vicharan.json) | 295 |
| [`pravachan-notes.json`](../../data/ihariprabodham/pravachan-notes.json) | 246 |
| [`discourses.json`](../../data/ihariprabodham/discourses.json) | 2,263 |

---

## What's in the corpus

- **Swamini Vato** — all 3,825 vato of Gunatitanand Swami across 16 prakaran, with the source's
  numbered footnote glosses rendered as a **Notes** list and the cross-references into the Vachanamrut.
- **Vachanamrut** — 274 discourses in 12 sections, each with its title; verse citations kept as blockquotes.
- **Prasang** — 965 incident-stories from the lives of the gurus, grouped into the source's 54 themes
  (Mahima, Dasatva, Seva, Bhakti…), each with its date and English title where the source gives one.
- **Kirtan** — 514 kirtan, shlok, aarti and dhun, tagged by their collection.
- **Pravachan Transcripts** — 232 full transcripts of daily pravachan of Guruhari Prabodhjivan Swamiji, by year.
- **Guruhari Paravani** — 541 quotes, attribution normalised to the two gurus (original kept in `guru_raw`).
- **Vicharan** and **Pravachan Notes** — dated darshan and discourse notes with their subjects and links.
- **Discourse Catalogue** — the full 2,263-record listing across 28 series (Akshar Vani, Hari Paramrut,
  Sant Vani…), as text and YouTube links; the videos themselves stay on YouTube.

## How it was made

`ihariprabodham.org` is a React app that reads its content from public, unauthenticated JSON files
and APIs. Nothing was decrypted and no login was used. The full text ships inline in the site's own
data files, or as clean reader HTML; those responses were mirrored verbatim into
[`_source/ihariprabodham/`](../../_source/ihariprabodham/), the app's private markup
(`$`, `${Title}`, `${Slok}`, `#ex1…`, `@`, `*#…#*`) was decoded exactly as for the paramrut corpus,
and reader HTML was reduced to its `title_gu` + `vaat_ind` reading pane. Nothing was reworded.

```bash
python3 tools/fetch_ihariprabodham.py            # rebuild everything (~cached HTML)
python3 tools/fetch_ihariprabodham.py prasang    # or a single collection
python3 tools/fetch_ihariprabodham.py --refetch-html
```

## A note on use

This is devotional material belonging to the HariPrabodham sampraday and remains theirs. It is
organised here to make reading and study easier — the words are unchanged and no claim is made over
them. If you intend to build on it or redistribute it further, ask the sampraday first.
