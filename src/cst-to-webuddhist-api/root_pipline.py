"""
Generate <name>_grouped.json from <name>.json.

Grouping rules:
  - bodytext + starts with number  → start a new group; strip the leading
                                     "N. " number; join following non-numbered
                                     bodytext segments with " ⤵ "
  - bodytext (no leading number)   → append to current group, or standalone
  - nikaya / book / title          → <h1>content</h1>
  - subsubhead / subhead           → <h2>content</h2>
  - chapter                        → <h3>content</h3>
  - centered / unindented / other  → plain content, unchanged

"""

import json
import re
import argparse
from pathlib import Path

HTML_TAG_MAP = {
    "nikaya":     "h1",
    "book":       "h1",
    "title":      "h1",
    "subsubhead": "h2",
    "subhead":    "h2",
    "chapter":    "h3",
}

SEPARATOR = " ⤵ "


def build_grouped(orig: dict) -> dict:
    segs = orig["segments"]
    title_pali = orig["title_pali"]

    output_segments: list[dict] = []
    current_group: list[str] | None = None
    current_segment_id: int | None = None
    current_chapter: int | None = None

    def flush():
        nonlocal current_group, current_segment_id
        if current_group is not None:
            entry: dict = {
                "seg-content": SEPARATOR.join(current_group),
                "segment_id": current_segment_id,
                "chapter": current_chapter,
            }
            output_segments.append(entry)
            current_group = None
            current_segment_id = None

    for seg in segs:
        css     = seg.get("css_class", "")
        content = seg["content"]
        chapter = seg.get("chapter")

        if css == "bodytext":
            if re.match(r"^\d+\.", content):
                flush()
                current_chapter = chapter
                num_match = re.match(r"^(\d+)\.", content)
                current_segment_id = int(num_match.group(1)) if num_match else None
                stripped = re.sub(r"^\d+\.\s*", "", content)
                current_group = [stripped]
            else:
                if current_group is not None:
                    current_group.append(content)
                else:
                    output_segments.append({"seg-content": content, "segment_id": None, "chapter": chapter})
        else:
            flush()
            tag = HTML_TAG_MAP.get(css)
            if tag:
                output_segments.append({"seg-content": f"<{tag}>{content}</{tag}>", "segment_id": None, "chapter": chapter})
            else:
                output_segments.append({"seg-content": content, "segment_id": None, "chapter": chapter})

    flush()

    full_content = " ".join(s["seg-content"] for s in output_segments)

    return {
        "type": "root",
        "title": {
            "en": title_pali,
            "bo": title_pali,
        },
        "language": "pi",
        "contributions": [
            {
                "person_id": "P12345678",
                "role": "author",
            }
        ],
        "category_id": "",
        "copyright": "Public domain",
        "license": "CC0",
        "segments": output_segments,
        "content": full_content,
    }


def main():
    root = Path(__file__).parents[2]

    parser = argparse.ArgumentParser(
        description="Generate <name>_grouped.json from <name>.json."
    )
    parser.add_argument(
        "stem",
        nargs="?",
        default="abh01m/abh01m",
        help=(
            "folder/filename stem, e.g. 'abh01m/abh01m' or just 'abh01m' "
            "(folder name is reused as filename). "
            "Alternatively pass two explicit paths as positional args."
        ),
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Explicit output path (optional; overrides stem-derived path).",
    )
    args = parser.parse_args()

    stem = Path(args.stem)
    name = stem.name
    folder = stem if stem.parent == Path(".") else stem.parent

    if args.output is not None:
        input_path  = Path(args.stem)
        output_path = Path(args.output)
    else:
        input_path  = root / folder / f"{name}.json"
        output_path = root / folder / f"{name}_grouped.json"

    with input_path.open(encoding="utf-8") as f:
        orig = json.load(f)

    doc = build_grouped(orig)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"Written {len(doc['segments'])} segments → {output_path}")


if __name__ == "__main__":
    main()
