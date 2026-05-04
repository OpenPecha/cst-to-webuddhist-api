import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ROOT_PATH = Path('data/alignment/root.json')
DEFAULT_COMMENTARY_PATH = Path('data/alignment/commentary.json')
DEFAULT_OUTPUT_PATH = Path('data/alignment/alignment.json')


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def normalize_segment_ids(segment_id: Any) -> tuple[int, ...]:
    """Return a tuple of segment IDs, or an empty tuple for unaligned spans."""
    if segment_id is None:
        return ()
    if isinstance(segment_id, list):
        return tuple(segment_id)
    return (segment_id,)


def spans_touch(previous: dict[str, int], current: dict[str, int]) -> bool:
    """Treat directly adjacent or overlapping spans as one continuous run."""
    return current['start'] <= previous['end'] + 1


def merge_consecutive(annotations: list[dict]) -> list[dict]:
    """Collapse contiguous annotations with the same normalized segment IDs."""
    merged: list[dict] = []
    cluster: dict | None = None

    for ann in annotations:
        segment_ids = normalize_segment_ids(ann.get('segment_id'))

        if (
            cluster is not None
            and segment_ids
            and segment_ids == cluster['segment_ids']
            and spans_touch(cluster['span'], ann['span'])
        ):
            cluster['span']['end'] = ann['span']['end']
        else:
            if cluster is not None:
                merged.append(cluster)
            cluster = {
                'span': {'start': ann['span']['start'], 'end': ann['span']['end']},
                'segment_ids': segment_ids,
            }

    if cluster is not None:
        merged.append(cluster)

    return merged


def assign_indices(merged: list[dict]) -> list[dict]:
    """Drop unaligned entries and assign sequential integer indices."""
    indexed: list[dict] = []

    for entry in merged:
        segment_ids = entry['segment_ids']
        if not segment_ids:
            continue
        indexed.append({
            'span': entry['span'],
            'segment_ids': segment_ids,
            'index': len(indexed),
        })

    return indexed


def build_root_occurrence_map(root_entries: list[dict]) -> dict[tuple[int, int], int]:
    """Map each (segment ID, occurrence) pair to its root entry order."""
    occurrence_counts: dict[int, int] = defaultdict(int)
    occurrence_map: dict[tuple[int, int], int] = {}

    for root_order, entry in enumerate(root_entries):
        for segment_id in entry['segment_ids']:
            occurrence_counts[segment_id] += 1
            occurrence = occurrence_counts[segment_id]
            occurrence_map[(segment_id, occurrence)] = root_order

    return occurrence_map


def build_alignment(
    root_data: dict[str, Any],
    commentary_data: dict[str, Any],
    *,
    target_manifestation_id: str,
) -> dict[str, Any]:
    """Build the alignment JSON from pre-loaded root and commentary data."""
    root_entries = assign_indices(merge_consecutive(root_data['annotation']))
    commentary_entries = assign_indices(merge_consecutive(commentary_data['annotations']))
    root_occurrence_map = build_root_occurrence_map(root_entries)

    referenced_root_orders: set[int] = set()
    alignment_links: list[dict] = []
    commentary_occurrences: dict[int, int] = defaultdict(int)

    for entry in commentary_entries:
        root_orders: list[int] = []
        for segment_id in entry['segment_ids']:
            commentary_occurrences[segment_id] += 1
            occurrence = commentary_occurrences[segment_id]
            root_order = root_occurrence_map.get((segment_id, occurrence))
            if root_order is not None:
                root_orders.append(root_order)

        if not root_orders:
            continue

        referenced_root_orders.update(root_orders)
        alignment_links.append({
            'span': entry['span'],
            'root_orders': root_orders,
        })

    root_order_to_target_index: dict[int, int] = {}
    target_annotation: list[dict] = []
    for root_order, entry in enumerate(root_entries):
        if root_order not in referenced_root_orders:
            continue
        root_order_to_target_index[root_order] = len(target_annotation)
        target_annotation.append({
            'span': entry['span'],
            'index': len(target_annotation),
        })

    alignment_annotation: list[dict] = []
    for link in alignment_links:
        alignment_annotation.append({
            'span': link['span'],
            'index': len(alignment_annotation),
            'alignment_index': [
                root_order_to_target_index[root_order]
                for root_order in link['root_orders']
            ],
        })

    return {
        'type': 'alignment',
        'target_manifestation_id': target_manifestation_id,
        'target_annotation': target_annotation,
        'alignment_annotation': alignment_annotation,
    }


def write_alignment(
    root_path: Path,
    commentary_path: Path,
    output_path: Path,
    *,
    target_manifestation_id: str,
) -> dict[str, Any]:
    root_data = load_json(root_path)
    commentary_data = load_json(commentary_path)
    result = build_alignment(
        root_data,
        commentary_data,
        target_manifestation_id=target_manifestation_id,
    )
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Build alignment JSON from root and commentary annotation files.',
    )
    parser.add_argument(
        '--root-path',
        type=Path,
        default=DEFAULT_ROOT_PATH,
        help=f'Root annotation JSON. Defaults to {DEFAULT_ROOT_PATH}',
    )
    parser.add_argument(
        '--commentary-path',
        type=Path,
        default=DEFAULT_COMMENTARY_PATH,
        help=f'Commentary annotation JSON. Defaults to {DEFAULT_COMMENTARY_PATH}',
    )
    parser.add_argument(
        '--output-path',
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f'Output alignment JSON path. Defaults to {DEFAULT_OUTPUT_PATH}',
    )
    parser.add_argument(
        '--target-manifestation-id',
        required=True,
        help='target_manifestation_id in the output (e.g. MNF12345678).',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = write_alignment(
        args.root_path,
        args.commentary_path,
        args.output_path,
        target_manifestation_id=args.target_manifestation_id,
    )
    n_target = len(result['target_annotation'])
    n_alignment = len(result['alignment_annotation'])
    print(
        f'{args.root_path} + {args.commentary_path}'
        f' → {args.output_path}'
        f' ({n_target} target, {n_alignment} alignment annotations)'
    )


if __name__ == '__main__':
    main()
