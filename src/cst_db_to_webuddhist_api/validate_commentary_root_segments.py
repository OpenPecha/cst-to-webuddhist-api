"""Validate one commentary segment count against the root segment count.

The commentary aṭṭhakathā annotations use list-valued ``segment_id`` entries,
while the Dhammasaṅgaṇī root uses scalar ``segment_id`` entries. This validator
groups consecutive annotations for one requested segment id, counts the groups
in commentary and root files, and checks that the counts are equal.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_COMMENTARY_PATH = PROJECT_ROOT / 'data/alignment/Dhammasaṅgaṇi-aṭṭhakathā.json'
DEFAULT_ROOT_PATH = PROJECT_ROOT / 'data/alignment/Dhammasaṅgaṇīpāḷi.json'


@dataclass(frozen=True)
class SegmentValidationResult:
    segment_id: int
    commentary_count: int
    root_count: int

    @property
    def matches(self) -> bool:
        return self.commentary_count == self.root_count


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def annotation_list(data: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    for key in ('annotation', 'annotations'):
        value = data.get(key)
        if isinstance(value, list):
            return value
    raise ValueError(f'{path} must contain an annotation or annotations list')


def normalize_segment_ids(value: Any) -> tuple[int, ...]:
    if value is None or value == []:
        return ()
    if isinstance(value, int):
        return (value,)
    if isinstance(value, str) and value.isdigit():
        return (int(value),)
    if isinstance(value, list):
        ids: list[int] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, int):
                ids.append(item)
            elif isinstance(item, str) and item.isdigit():
                ids.append(int(item))
            else:
                raise ValueError(f'Unsupported segment_id value in list: {item!r}')
        return tuple(dict.fromkeys(ids))
    raise ValueError(f'Unsupported segment_id value: {value!r}')


def count_segment_runs(annotations: list[dict[str, Any]], segment_id: int) -> int:
    count = 0
    previous_has_segment = False

    for annotation in annotations:
        current_ids = normalize_segment_ids(annotation.get('segment_id'))
        has_segment = segment_id in current_ids
        if not has_segment:
            previous_has_segment = False
            continue
        if previous_has_segment:
            continue

        count += 1
        previous_has_segment = True

    return count


def validate_segment_count(
    commentary_annotations: list[dict[str, Any]],
    root_annotations: list[dict[str, Any]],
    segment_id: int,
) -> SegmentValidationResult:
    return SegmentValidationResult(
        segment_id=segment_id,
        commentary_count=count_segment_runs(commentary_annotations, segment_id),
        root_count=count_segment_runs(root_annotations, segment_id),
    )


def build_report(
    commentary_path: Path = DEFAULT_COMMENTARY_PATH,
    root_path: Path = DEFAULT_ROOT_PATH,
    segment_id: int = 1,
) -> dict[str, Any]:
    commentary_annotations = annotation_list(load_json(commentary_path), commentary_path)
    root_annotations = annotation_list(load_json(root_path), root_path)
    result = validate_segment_count(commentary_annotations, root_annotations, segment_id)

    return {
        'ok': result.matches,
        'commentary_path': str(commentary_path),
        'root_path': str(root_path),
        'segment_id': result.segment_id,
        'commentary_count': result.commentary_count,
        'root_count': result.root_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Validate one commentary segment-id run count against the root run count.',
    )
    parser.add_argument(
        'commentary_path',
        type=Path,
        help='Commentary annotation JSON.',
    )
    parser.add_argument(
        'root_path',
        type=Path,
        help='Root annotation JSON.',
    )
    parser.add_argument(
        'segment_id',
        type=int,
        help='Segment id to count in both files.',
    )
    parser.add_argument(
        '--report-path',
        type=Path,
        help='Optional path to write the full JSON validation report.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.commentary_path, args.root_path, args.segment_id)

    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write('\n')

    if report['ok']:
        print(
            f"OK: segment_id={report['segment_id']} has "
            f"{report['commentary_count']} consecutive run(s) in both commentary and root."
        )
    else:
        print(
            f"FAILED: segment_id={report['segment_id']} has different consecutive run counts "
            f"(commentary={report['commentary_count']}, root={report['root_count']})."
        )

    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
