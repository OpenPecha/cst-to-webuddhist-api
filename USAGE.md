# Usage Manual

All commands are run from the project root. Python 3.10+ required. No third-party packages.

## Folder layout

```
data/
├── input/      # Raw CST JSON files (source texts)
├── output/     # Processed annotation JSON (commentary pipeline output)
├── alignment/  # Root text JSON + alignment JSON files
├── upload/     # WebBuddha API upload payloads
└── review/     # Alignment review samples for QA
```

---

## Pipeline overview

```
data/input/  ──[1]──►  data/output/  ──[3]──►  data/upload/
                │
                └──[2]──►  data/alignment/  ──[4]──►  data/review/
                  (+ root text)
```

---

## Step 1 — Process CST input → output

Converts raw CST JSON files into span-annotated WebBuddha JSON.

```bash
python3 src/cst-db-to-webuddhist-api/commentary_pipeline.py \
  --language pi-roman \
  --input-dir data/input \
  --output-dir data/output
```

| Argument | Required | Description |
|---|---|---|
| `--language` | yes | Language code for the output (e.g. `pi-roman`, `pi-thai`) |
| `--input-dir` | no | Raw CST JSON folder. Default: `data/input` |
| `--output-dir` | no | Output folder. Default: `data/output` |

---

## Step 2 — Build alignment

Aligns a commentary output file against a root text JSON.

The root text JSON must have an `annotation` list and a `content` field (full base text string). The commentary JSON is the output from Step 1.

```bash
python3 src/cst-db-to-webuddhist-api/alignment_pipeline.py \
  --root-path data/alignment/Dhammasaṅgaṇīpāḷi.json \
  --commentary-path data/output/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json \
  --output-path data/alignment/Dhammasaṅgaṇi-aṭṭhakathā_alignment.json \
  --target-manifestation-id MNF12345678
```

| Argument | Required | Description |
|---|---|---|
| `--target-manifestation-id` | yes | Manifestation ID of the root text in the target system |
| `--root-path` | no | Root annotation JSON. Default: `data/alignment/root.json` |
| `--commentary-path` | no | Commentary annotation JSON. Default: `data/alignment/commentary.json` |
| `--output-path` | no | Output alignment JSON. Default: `data/alignment/alignment.json` |

---

## Step 3 — Generate upload payload

Builds a WebBuddha API upload payload from a processed output file.

```bash
python3 src/cst-db-to-webuddhist-api/commentary_upload.py \
  data/output/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json \
  data/upload/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json \
  --person-id YOUR_PERSON_ID \
  --category-id YOUR_CATEGORY_ID
```

Add `--post --instance-id INSTANCE_ID` to also POST to the API.

| Argument | Required | Description |
|---|---|---|
| `input_path` (positional) | no | Processed JSON. Default: example aṭṭhakathā file |
| `output_path` (positional) | no | Upload payload destination. Default: example upload path |
| `--person-id` | yes | Author person ID |
| `--category-id` | yes | Category ID |
| `--copyright` | no | Copyright string. Default: `Public domain` |
| `--license` | no | License string. Default: `CC0` |
| `--post` | no | POST payload to the API |
| `--instance-id` | if `--post` | WebBuddha instance ID |
| `--api-base-url` | no | API base URL |
| `--header` | no | Extra HTTP header (`Key: Value`). Repeatable |

---

## Step 4 — Generate alignment review file

Randomly samples alignment pairs for human QA.

```bash
python3 src/cst-db-to-webuddhist-api/alignment_tester.py \
  data/output/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json \
  20 \
  --alignment-path data/alignment/Dhammasaṅgaṇi-aṭṭhakathā_alignment.json \
  --root-path data/alignment/Dhammasaṅgaṇīpāḷi.json \
  --output-dir data/review
```

Writes `data/review/<commentary-stem>_alignment_review.json`.

| Argument | Required | Description |
|---|---|---|
| `commentary_file` (positional) | yes | Commentary output JSON (must have `base_content`) |
| `n_segments` (positional) | yes | Number of random alignment pairs to sample |
| `--alignment-path` | no | Alignment JSON. Default: `data/alignment/alignment.json` |
| `--root-path` | no | Root JSON (must have `content`). Default: `data/alignment/root.json` |
| `--output-dir` | no | Review output folder. Default: `data/review` |
| `--seed` | no | Random seed for reproducible sampling |

---

## Step 5 — Inspect a specific segment (development tool)

Prints the text for a given `segment_id` from a processed output file.

```bash
python3 src/cst-db-to-webuddhist-api/segment_tester.py \
  data/output/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json \
  1
```

```bash
# Optional: also filter by chapter
python3 src/cst-db-to-webuddhist-api/segment_tester.py \
  data/output/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json \
  1 2
```

---

## Step 6 — Validate segment counts (development tool)

Checks that a segment ID appears the same number of times in the commentary and root.

```bash
python3 src/cst-db-to-webuddhist-api/validate_commentary_root_segments.py \
  data/alignment/Dhammasaṅgaṇi-aṭṭhakathā.json \
  data/alignment/Dhammasaṅgaṇīpāḷi.json \
  1
```

---

## Run tests

```bash
pytest
```
