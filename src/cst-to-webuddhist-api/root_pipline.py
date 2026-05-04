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

NUMBERED     = re.compile(r"^\d+\.")
STRIP_NUMBER = re.compile(r"^\d+\.\s*")
CAPTURE_NUM  = re.compile(r"^(\d+)\.")

H1_CLASSES = {"nikaya", "book", "title"}
H2_CLASSES = {"subsubhead", "subhead"}
H3_CLASSES = {"chapter"}
HEADING_CLASSES = H1_CLASSES | H2_CLASSES | H3_CLASSES

SEPARATOR = " ⤵ "


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

    for seg in segments:
        css     = seg.get("css_class", "")
        content = seg["content"]
        chapter = seg.get("chapter")

        if css in HEADING_CLASSES:
            flush()
            result.append({"seg-content": make_heading(css, content), "segment_id": None, "chapter": chapter})

        elif css == "bodytext":
            if NUMBERED.match(content):
                flush()
                group_chapter = chapter
                group_id      = extract_segment_id(content)
                group_parts   = [STRIP_NUMBER.sub("", content)]
            elif group_parts is not None:
                group_parts.append(content)
            else:
                result.append({"seg-content": content, "segment_id": None, "chapter": chapter})

        else:
            flush()
            result.append({"seg-content": content, "segment_id": None, "chapter": chapter})

    flush()
    return result


def generate_metadata(data: dict) -> dict:
    title_pali = data["title_pali"]
    return {
        "type": "root",
        "title": {"en": title_pali, "bo": title_pali},
        "language": "pi",
        "contributions": [{"person_id": "P12345678", "role": "author"}],
        "category_id": "",
        "copyright": "Public domain",
        "license": "CC0",
    }


def process_file(input_path: Path, output_path: Path) -> None:
    with input_path.open(encoding="utf-8") as f:
        data = json.load(f)

    segments     = parse_segments(data["segments"])
    full_content = " ".join(s["seg-content"] for s in segments)

    result = {**generate_metadata(data), "segments": segments, "content": full_content}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Written {len(segments)} segments → {output_path}")


def resolve_paths(stem_arg: str, output_arg: str | None) -> tuple[Path, Path]:
    if output_arg is not None:
        return Path(stem_arg), Path(output_arg)

    root   = Path(__file__).parents[2]
    stem   = Path(stem_arg)
    name   = stem.name
    folder = stem if stem.parent == Path(".") else stem.parent
    return root / folder / f"{name}.json", root / folder / f"{name}_grouped.json"


def main():
    parser = argparse.ArgumentParser(
        description="Generate <name>_grouped.json from <name>.json."
    )
    parser.add_argument(
        "stem",
        help=(
            "Folder/filename stem, e.g. 'abh01m/abh01m' or just 'abh01m' "
            "(folder name is reused as filename)."
        ),
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Explicit output path (optional; overrides stem-derived path).",
    )
    args = parser.parse_args()

    input_path, output_path = resolve_paths(args.stem, args.output)
    process_file(input_path, output_path)


if __name__ == "__main__":
    main()
