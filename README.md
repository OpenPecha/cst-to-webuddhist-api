<h1 align="center">
  <br>
  <a href="https://openpecha.org"><img src="https://avatars.githubusercontent.com/u/82142807?s=400&u=19e108a15566f3a1449bafb03b8dd706a72aebcd&v=4" alt="OpenPecha" width="150"></a>
  <br>
  cst-db-to-webuddhist-api
  <br>
</h1>

A pipeline that converts Chaṭṭha Saṅgāyana Tipiṭaka (CST) database JSON files into structured JSON for the WebBuddha API — with character-span annotations and root-text alignment.

## Owner(s)

- [@ta4tsering](https://github.com/ta4tsering)

## Table of contents

<p align="center">
  <a href="#project-description">Project description</a> •
  <a href="#who-this-project-is-for">Who this project is for</a> •
  <a href="#project-dependencies">Project dependencies</a> •
  <a href="#instructions-for-use">Instructions for use</a> •
  <a href="#output-format">Output format</a> •
  <a href="#how-to-get-help">How to get help</a> •
  <a href="#terms-of-use">Terms of use</a>
</p>
<hr>

## Project description

`cst-db-to-webuddhist-api` converts raw CST segment JSON files (mūla, aṭṭhakathā, ṭīkā) into a normalised format suitable for the WebBuddha API. It produces a single JSON per text with:

- **Metadata** — language, title, and source attribution
- **Base content** — all segments joined into one continuous string
- **Annotations** — per-segment character spans (exclusive end) with root-text alignment via `segment_id` and `chapter`

Segment numbers embedded in commentary texts (e.g. `1. Katame dhammā…`) are used as alignment keys that map each commentary passage back to the corresponding root-text segment.

## Who this project is for

Developers and researchers working on the WebBuddha platform or any system that needs structured, span-annotated Pali texts from the CST corpus.

## Project dependencies

- Python ≥ 3.10
- No third-party packages — stdlib only (`json`, `re`, `pathlib`)

## Instructions for use

### Quick start

```bash
# 1. Process CST input
python3 -m cst_db_to_webuddhist_api.commentary_pipeline --language pi-roman

# 2. Build alignment (requires root text JSON and manifestation ID)
python3 -m cst_db_to_webuddhist_api.alignment_pipeline \
  --root-path data/alignment/<root>.json \
  --commentary-path data/output/<text>.json \
  --output-path data/alignment/<text>_alignment.json \
  --target-manifestation-id MNF12345678

# 3. Generate upload payload
python3 -m cst_db_to_webuddhist_api.commentary_upload \
  data/output/<text>.json data/upload/<text>.json \
  --person-id YOUR_PERSON_ID --category-id YOUR_CATEGORY_ID

# Run tests
pytest
```

All data lives under `data/`: `input/` (raw CST), `output/` (processed), `alignment/`, `upload/`, `review/`.

## Output format

Each output JSON has this structure:

```json
{
  "language": "pli",
  "title": "Dhammasaṅgaṇi-aṭṭhakathā (Commentary)",
  "source": "Chaṭṭha Saṅgāyana Tipiṭaka (CST), https://tipitaka.app/",
  "base_content": "<all segments joined by newline>",
  "annotations": [
    {
      "span": { "start": 0, "end": 46 },
      "segment_id": null,
      "chapter": 0
    },
    {
      "span": { "start": 120816, "end": 122389 },
      "segment_id": 1,
      "chapter": 2
    }
  ]
}
```

**Fields:**

| Field | Description |
|---|---|
| `base_content[span.start:span.end]` | Recovers the exact text of that segment |
| `segment_id` | Integer stripped from the segment's leading number; `null` for headings and unnumbered passages |
| `chapter` | Chapter index from the source JSON; disambiguates segments that share the same `segment_id` across different sections |

The pair `(chapter, segment_id)` uniquely identifies a root-text alignment target within a file.

## How to get help

- File an issue on GitHub
- Email us at openpecha[at]gmail.com
- Join our [Discord](https://discord.com/invite/7GFpPFSTeA)

## Terms of use

Licensed under the [MIT License](/LICENSE).
