#!/usr/bin/env python3
"""Canonical theme taxonomy unifying the two source vocabularies.

Two sources tag content thematically:
  - Prasang: 54 category ids (many are the same theme split across the two gurus'
    lineages) — held in _source/ihariprabodham/prasang-categories.json (gu + en).
  - Swamini Vato: 33 topics — held in data/topics.json (gu + translit).

Here we map both onto ONE canonical set of theme slugs. Only the English slug and the
merge decisions are authored here; every Gujarati string is taken verbatim from the
source data, so no Gujarati is ever retyped (accuracy first).
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Prasang category id -> canonical slug. Ids 1-14 (Swamishri lineage) and 15-28
# (Prabodhjivan lineage) repeat the same themes; both fold to one slug.
PRASANG_CAT = {
    1: "jivan-darshan", 15: "jivan-darshan",
    2: "adhyatmik-suj", 16: "adhyatmik-suj",
    3: "divya-anubhav", 17: "divya-anubhav",
    4: "divya-darshan", 18: "divya-darshan",
    5: "raksha", 19: "raksha",
    6: "ashirvad", 20: "ashirvad",
    7: "swarupnishtha", 21: "swarupnishtha",
    8: "jivanbhavana",
    9: "abhav-avagun", 24: "dasatva", 10: "dasatva",
    11: "bhaktoni-bhakti", 28: "bhaktoni-bhakti",
    12: "gurubhakti", 27: "gurubhakti",
    13: "suhradbhav", 32: "suhradbhav",
    14: "mahima", 51: "mahima",
    22: "prabhu-bhakti",
    23: "akshar-sparsh",
    25: "yuva-pravruti",
    26: "bal-pravruti",
    29: "seva",
    30: "swami-sevak-bhav",
    31: "swamini-vato",
    33: "sambandhno-mahima",
    34: "bhajan",
    35: "sabha",
    36: "kathavarta",
    37: "ambrish",
    38: "swadharm",
    39: "saralata",
    40: "nirdoshbuddhi",
    41: "aksharbrahm",
    42: "upasana",
    43: "antaryami",
    44: "olakhan",
    45: "pragatya",
    46: "abhyas",
    47: "agya-palan",
    48: "vishvas",
    49: "prarthana",
    50: "smruti",
    52: "nishtha",
    53: "bhagavadi",
    54: "nimit",
}

# Swamini Vato topic id -> canonical slug. Shared themes fold onto the prasang slug;
# vato-only themes get their own slug.
VATO_TOPIC = {
    1: "sarvopari-bhagavan",
    2: "mahima",                       # Sadhuno Mahima
    3: "nishchay",
    4: "asharo",
    5: "abhav-avagun",
    6: "kathavarta",
    7: "antardrasti",
    8: "divyabhav-manushyabhav",
    9: "bhajan",
    10: "atmanishtha",
    11: "anuvruti-abhipray",
    12: "anusandhan",
    13: "sadhu-samagam",
    14: "bhagavadi",
    15: "jiv-jadavo",
    16: "dosh",
    17: "dehabhiman",
    18: "maya",
    19: "moksh",
    20: "sadhupanu",
    21: "suhradbhav",                  # Suhradpanu
    22: "swarupnishtha",
    23: "shraddha",
    24: "ruchi",
    25: "satsang",
    26: "kusang",
    27: "satsangi",
    28: "mahima",                      # Swaminarayan Mantrno Mahima
    29: "sankhyagnan",
    30: "upasana",                     # Sarvopari Upasana
    31: "sang",
    32: "bhagavanni-karuna",
    33: "gunatitanand-vyaktitva",
}

# Preferred English display name per slug (title-cased where the source had none/dupes)
EN = {
    "jivan-darshan": "Jivan Darshan", "adhyatmik-suj": "Adhyatmik Suj",
    "divya-anubhav": "Divya Anubhav", "divya-darshan": "Divya Darshan",
    "raksha": "Raksha", "ashirvad": "Ashirvad", "swarupnishtha": "Swarupnishtha",
    "jivanbhavana": "Jivanbhavana", "abhav-avagun": "Abhav-Avagun", "dasatva": "Dasatva",
    "bhaktoni-bhakti": "Bhaktoni Bhakti", "gurubhakti": "Gurubhakti",
    "suhradbhav": "Suhradbhav", "mahima": "Mahima", "prabhu-bhakti": "Prabhu Bhakti",
    "akshar-sparsh": "Akshar Sparsh", "yuva-pravruti": "Yuva Pravruti",
    "bal-pravruti": "Bal Pravruti", "seva": "Seva", "swami-sevak-bhav": "Swami Sevak Bhav",
    "swamini-vato": "Swamini Vato", "sambandhno-mahima": "Sambandhno Mahima",
    "bhajan": "Bhajan", "sabha": "Sabha", "kathavarta": "Kathavarta", "ambrish": "Ambrish",
    "swadharm": "Swadharm", "saralata": "Saralata", "nirdoshbuddhi": "Nirdoshbuddhi",
    "aksharbrahm": "Aksharbrahm", "upasana": "Upasana", "antaryami": "Antaryami",
    "olakhan": "Olakhan", "pragatya": "Pragatya Harinu", "abhyas": "Abhyas",
    "agya-palan": "Agya Palan", "vishvas": "Vishvas", "prarthana": "Prarthana",
    "smruti": "Smruti", "nishtha": "Nishtha", "bhagavadi": "Bhagavadi", "nimit": "Nimit",
    "sarvopari-bhagavan": "Sarvopari Bhagavan Swaminarayan", "nishchay": "Nishchay",
    "asharo": "Asharo", "antardrasti": "Antardrasti",
    "divyabhav-manushyabhav": "Divyabhav ne Manushyabhav", "atmanishtha": "Atmanishtha",
    "anuvruti-abhipray": "Anuvruti-Abhipray", "anusandhan": "Anusandhan",
    "sadhu-samagam": "Sadhu Samagam", "jiv-jadavo": "Jiv Jadavo", "dosh": "Dosh",
    "dehabhiman": "Dehabhiman", "maya": "Maya", "moksh": "Moksh", "sadhupanu": "Sadhupanu",
    "shraddha": "Shraddha", "ruchi": "Ruchi", "satsang": "Satsang", "kusang": "Kusang",
    "satsangi": "Satsangina Satsangi", "sankhyagnan": "Sankhyagnan", "sang": "Sang",
    "bhagavanni-karuna": "Bhagavanni Karuna", "gunatitanand-vyaktitva": "Gunatitanand Swaminu Vyaktitva",
}


def build_taxonomy():
    """Return {slug: {slug, gu, en, from_prasang:[ids], from_vato:[ids]}} with gu taken
    verbatim from source data."""
    pc = json.loads((ROOT / "_source/ihariprabodham/prasang-categories.json").read_text())
    pc = {int(k): v for k, v in pc.items()}
    vt = {t["id"]: t for t in json.loads((ROOT / "data/topics.json").read_text())}

    themes = {}
    def ensure(slug):
        if slug not in themes:
            themes[slug] = {"slug": slug, "en": EN.get(slug, slug.replace("-", " ").title()),
                            "gu": None, "from_prasang": [], "from_vato": []}
        return themes[slug]

    for cid, slug in PRASANG_CAT.items():
        t = ensure(slug); t["from_prasang"].append(cid)
        if not t["gu"] and cid in pc:
            t["gu"] = pc[cid]["gu"].strip()
    for tid, slug in VATO_TOPIC.items():
        t = ensure(slug); t["from_vato"].append(tid)
        if not t["gu"] and tid in vt:
            t["gu"] = (vt[tid].get("name_gu") or "").strip() or None
    # order by english name
    return dict(sorted(themes.items(), key=lambda kv: kv[1]["en"].lower()))


def prasang_theme(cat_id):
    return PRASANG_CAT.get(int(cat_id)) if cat_id not in (None, 0, "0") else None


def vato_themes(vat_id, topics_index):
    """topics_index: {topic_id: set(vat_ids)} → return slugs for a given vato id."""
    out = []
    for tid, ids in topics_index.items():
        if vat_id in ids and tid in VATO_TOPIC:
            s = VATO_TOPIC[tid]
            if s not in out:
                out.append(s)
    return out


if __name__ == "__main__":
    tx = build_taxonomy()
    (ROOT / "data/tags.json").write_text(
        json.dumps(list(tx.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    miss = [s for s, t in tx.items() if not t["gu"]]
    print(f"{len(tx)} canonical themes → data/tags.json")
    print(f"  prasang cats mapped: {len(PRASANG_CAT)} · vato topics mapped: {len(VATO_TOPIC)}")
    if miss:
        print("  WARNING no gu for:", miss)
