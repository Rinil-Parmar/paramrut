[← Paramrut](../README.md)

# Data

The same corpus as [`text/`](../text/README.md), as UTF-8 JSON — one file per collection,
each a flat array of records.

| File | Records | Size | Fields |
|---|---:|---:|---|
| [`swamini-vato.json`](swamini-vato.json) | 3,825 | 8.5 MB | `vat_id`, `prakaran`, `vat_no`, `title_gu/hi/en`, `text.{gu,hi,en}`, `footnotes`, `ref` |
| [`vachanamrut.json`](vachanamrut.json) | 274 | 2.8 MB | `id`, `section`, `number`, `name_gu`, `title_gu`, `tithi`, `date`, `weekday`, `text`, `highlights` |
| [`anirdeshi-amrut.json`](anirdeshi-amrut.json) | 1,549 | 2.3 MB | `id`, `date`, `kalash`, `achaman`, `title`, `tags`, `text` |
| [`shikshapatri.json`](shikshapatri.json) | 212 | 190 KB | `number`, `sanskrit`, `gujarati`, `hindi`, `selected` |
| [`quotes.json`](quotes.json) | 541 | 263 KB | `number`, `quote`, `guru`, `guru_raw`, `date_gu`, `place` |
| [`parisishth.json`](parisishth.json) | 83 | 95 KB | `id`, `title_gu`, `title_translit`, `text` |
| [`topics.json`](topics.json) | 33 | 8 KB | `id`, `name_gu`, `name_translit`, `vat_ids` |
| [`index.json`](index.json) | — | 1 KB | provenance and record counts for every collection |

## Notes on the fields

- **`text`** is plain text with paragraphs separated by blank lines. On Swamini Vato it is an
  object keyed by language (`gu`, `hi`, `en`) holding only the languages that exist for that vato.
- **`footnotes`** are the source's numbered glosses, parsed into `{n, term, meaning}`.
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
by_id  = {v['vat_id']: v for v in vato}
for i in mahima['vat_ids']:
    print(by_id[i]['text']['gu'])
```
