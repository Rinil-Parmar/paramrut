---
title: Paramrut Corpus
tags:
  - corpus
---

# Paramrut — Unified Corpus

**11,522 records** of the HariPrabodham sampraday's scripture, prasang, pravachan and paravani — deduplicated from the Paramrut app and ihariprabodham.org, structured, and tagged.

The text is unchanged. Structure, YAML tags (Obsidian-ready) and a theme index are added.

## Read

| Section | Contents |
|---|---|
| 📖 **[Granth](text/granth/README.md)** | Swamini Vato, Vachanamrut, Anirdeshi Amrut, Ambrish Upnishad, Brahm Ratna, Shikshapatri, Kirtan |
| 📿 **[Prasang](text/prasang/README.md)** | 965 incident-stories, by theme |
| 🗣️ **[Pravachan](text/pravachan/README.md)** | transcripts, Hari Amrut, discourse catalogue |
| 💬 **[Paravani](text/paravani.md)** | 541 quotes |
| 📇 **[Parisishth](text/parisishth.md)** | 83 glossary & bios |
| 🧭 **[Vicharan](text/vicharan.md)** | 295 dated darshan |
| 🏷️ **[Themes](tags/README.md)** | browse by subject across 65 themes |

## Query

**[`data/`](data/)** holds per-item JSON with structural + theme tags — one array per collection, plus [`tags.json`](data/tags.json) (the taxonomy). Every record carries `themes`, `type`, `source`, `lang`.

## Tagging

Every page has YAML frontmatter (Obsidian Properties): `type`, `work`, `section`, `themes`, `source`, and nested `tags` (`type/granth`, `granth/vachanamrut`, `theme/mahima`). Point an Obsidian vault at this folder to browse by tag and graph.

## Sources & dedup

See [`PROVENANCE.md`](PROVENANCE.md) — which source each work came from and how the four overlapping works were deduplicated (richer copy kept).

