"""
Convert data/input/<folder>/<file>.json into two outputs:

  data/output/root/<folder>/<file>.json            – root document
  data/output/root/<folder>/<file>_annotation.json – span annotations

Grouping rules (root document):
  - bodytext + starts with number  → start a new group; strip the leading
                                     "N. " number; join following non-numbered
                                     bodytext segments with " ⤵ "
  - bodytext (no leading number)   → append to current group, or standalone
  - hangnum                        → start a new gatha group; its number
                                     becomes the segment_id for the group
  - gatha1/gatha2/gatha3/gatha4   → append to current gatha group
  - gathalast                      → append to current gatha group, then flush
                                     the whole stanza as one entry (joined with
                                     " ⤵ "); segment_id taken from hangnum
  - nikaya / book / title          → <h1>content</h1>
  - subsubhead / subhead           → <h2>content</h2>
  - chapter                        → <h3>content</h3>
  - centered / unindented / other  → plain content, unchanged

Annotation rules:
  - Each segment span marks the character indices of seg-content inside
    the full content string.
  - Every span (except the last) is extended to include the trailing
    separator so that consecutive spans are contiguous.
"""

import json
import re
import argparse
from pathlib import Path

NUMBERED     = re.compile(r"^\d+\.")
STRIP_NUMBER = re.compile(r"^\d+\.\s*")
CAPTURE_NUM  = re.compile(r"^(\d+)\.")
GATHA_CLASSES = {'gatha1', 'gatha2', 'gatha3','gatha4', 'gathalast'}
H1_CLASSES = {"nikaya", "book", "title"}
H2_CLASSES = {"subsubhead", "subhead"}
H3_CLASSES = {"chapter"}
HEADING_CLASSES = H1_CLASSES | H2_CLASSES | H3_CLASSES

SEPARATOR = " ⤵ "


# ---------------------------------------------------------------------------
# Root-document helpers
# ---------------------------------------------------------------------------

def make_heading(css: str, content: str) -> str:
    if css in H1_CLASSES:
        return f"<h1>{content}</h1>"
    if css in H2_CLASSES:
        return f"<h2>{content}</h2>"
    return f"<h3>{content}</h3>"


def extract_segment_id(content: str) -> int | None:
    m = CAPTURE_NUM.match(content)
    return int(m.group(1)) if m else None


def parse_segments(segments: list[dict]) -> list[dict]:
    result: list[dict] = []
    group_parts  : list[str] | None = None
    group_id     : int | None       = None
    group_chapter: int | None       = None

    # pending gatha state
    gatha_parts  : list[str] | None = None
    gatha_id     : int | None       = None
    gatha_chapter: int | None       = None

    def flush():
        nonlocal group_parts, group_id
        if group_parts is not None:
            result.append({
                "seg-content": SEPARATOR.join(group_parts),
                "segment_id":  group_id,
                "chapter":     group_chapter,
            })
            group_parts = None
            group_id    = None

    def flush_gatha():
        nonlocal gatha_parts, gatha_id, gatha_chapter
        if gatha_parts is not None:
            result.append({
                "seg-content": SEPARATOR.join(gatha_parts),
                "segment_id":  gatha_id,
                "chapter":     gatha_chapter,
            })
            gatha_parts   = None
            gatha_id      = None
            gatha_chapter = None

    for seg in segments:
        css     = seg.get("css_class", "")
        content = seg["content"]
        chapter = seg.get("chapter")

        if css in HEADING_CLASSES:
            flush()
            flush_gatha()
            result.append({"seg-content": make_heading(css, content), "segment_id": None, "chapter": chapter})

        elif css == "bodytext":
            flush_gatha()
            if NUMBERED.match(content):
                flush()
                group_chapter = chapter
                group_id      = extract_segment_id(content)
                group_parts   = [STRIP_NUMBER.sub("", content)]
            elif group_parts is not None:
                group_parts.append(content)
            else:
                result.append({"seg-content": content, "segment_id": None, "chapter": chapter})

        elif css == "hangnum":
            flush()
            flush_gatha()
            gatha_id      = extract_segment_id(content)
            gatha_chapter = chapter
            gatha_parts   = []

        elif css in GATHA_CLASSES:
            if gatha_parts is None:
                gatha_parts   = []
                gatha_chapter = chapter
            gatha_parts.append(content)
            if css == "gathalast":
                flush_gatha()

        else:
            flush()
            flush_gatha()
            result.append({"seg-content": content, "segment_id": None, "chapter": chapter})

    flush()
    flush_gatha()
    return result


def generate_metadata(data: dict, lang: str) -> dict:
    title_pali = data["title_pali"]
    return {
        "type": "root",
        "title": {"en": title_pali, f"{lang}": title_pali},
        "language": lang,
        "contributions": [{"person_id": "h6qJbs33NdZAQDdr9C3ir", "role": "author"}],
        "category_id": "iGzbJ0D6zdyccIv2gnXeI",
        "copyright": "Public domain",
        "license": "CC0",
    }


def build_root_doc(data: dict, lang: str) -> dict:
    segments     = parse_segments(data["segments"])
    full_content = " ".join(s["seg-content"] for s in segments)
    return {**generate_metadata(data, lang), "segments": segments, "content": full_content}


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------

def build_annotation_doc(root_doc: dict) -> dict:
    segments = root_doc.get("segments", [])
    content: str = root_doc.get("content", "")

    annotations: list[dict] = []
    search_from = 0

    for i, seg in enumerate(segments):
        text    = seg.get("seg-content", "")
        is_last = i == len(segments) - 1
        start   = content.index(text, search_from)
        text_end = start + len(text) - 1

        if is_last:
            end = text_end
        else:
            next_text  = segments[i + 1].get("seg-content", "")
            next_start = content.index(next_text, text_end + 1)
            end = next_start - 1

        annotations.append({
            "span":       {"start": start, "end": end},
            "segment_id": seg.get("segment_id"),
        })
        search_from = end + 1

    return {
        "metadata": {
            "type":     "critical",
            "source":   root_doc.get("source", "https://tipitaka.app/"),
        },
        "annotation": annotations,
        "content":    content,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def resolve_paths(folder_name: str, file_stem: str) -> tuple[Path, Path, Path]:
    repo_root        = Path(__file__).parents[3]
    base             = repo_root / "data" / "output" / "root" / folder_name
    input_path       = repo_root / "data" / "input"  / folder_name / f"{file_stem}.json"
    root_out         = base / f"{file_stem}.json"
    annotation_out   = base / f"{file_stem}_annotation.json"
    return input_path, root_out, annotation_out


def process_file(input_path: Path, root_out: Path, annotation_out: Path, lang: str) -> None:
    with input_path.open(encoding="utf-8") as f:
        data = json.load(f)

    root_doc       = build_root_doc(data, lang)
    annotation_doc = build_annotation_doc(root_doc)

    root_out.parent.mkdir(parents=True, exist_ok=True)

    with root_out.open("w", encoding="utf-8") as f:
        json.dump(root_doc, f, ensure_ascii=False, indent=2)
    print(f"Written {len(root_doc['segments'])} segments → {root_out}")

    with annotation_out.open("w", encoding="utf-8") as f:
        json.dump(annotation_doc, f, ensure_ascii=False, indent=2)
    print(f"Written {len(annotation_doc['annotation'])} annotations → {annotation_out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Convert data/input/<folder>/<file>.json → "
            "data/output/root/<folder>/<file>.json + <file>_annotation.json"
        )
    )
    parser.add_argument(
        "folder_name",
        help="Sub-folder under data/input/, e.g. 'Dhammapadapāḷi'.",
    )
    parser.add_argument(
        "file",
        help="JSON filename stem (without .json), e.g. 's0502m'.",
    )
    parser.add_argument(
        "--lang",
        help="Language code written into the root metadata (default: pi).",
    )
    args = parser.parse_args()

    input_path, root_out, annotation_out = resolve_paths(args.folder_name, args.file)
    process_file(input_path, root_out, annotation_out, args.lang)


if __name__ == "__main__":
    main()
