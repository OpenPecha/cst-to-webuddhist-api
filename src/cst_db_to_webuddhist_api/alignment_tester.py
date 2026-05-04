import argparse
import json
import random
from pathlib import Path
from typing import Any


DEFAULT_ALIGNMENT_PATH = Path('data/alignment/alignment.json')
DEFAULT_ROOT_PATH = Path('data/alignment/root.json')
DEFAULT_REVIEW_DIR = Path('data/review')


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def build_index_to_span(target_annotation: list[dict]) -> dict[int, dict]:
    """Map each target_annotation index → its span dict."""
    return {entry['index']: entry['span'] for entry in target_annotation}


def sample_alignments(
    commentary_path: Path,
    n_segments: int,
    *,
    alignment_path: Path = DEFAULT_ALIGNMENT_PATH,
    root_path: Path = DEFAULT_ROOT_PATH,
    seed: int | None = None,
    output_dir: Path = DEFAULT_REVIEW_DIR,
) -> Path:
    """Sample n_segments random alignment pairs and write a review JSON.

    Each entry in the output shows the commentary segment and the corresponding
    root basetext segment(s) side by side for human review.
    """
    commentary_data = load_json(commentary_path)
    alignment_data = load_json(alignment_path)
    root_data = load_json(root_path)

    commentary_text: str = commentary_data['base_content']
    root_text: str = root_data['content']

    target_index_to_span = build_index_to_span(alignment_data['target_annotation'])
    alignment_annotation: list[dict] = alignment_data['alignment_annotation']

    if n_segments > len(alignment_annotation):
        raise ValueError(
            f'Requested {n_segments} segments but only '
            f'{len(alignment_annotation)} alignment entries exist.'
        )

    rng = random.Random(seed)
    sampled = rng.sample(alignment_annotation, n_segments)
    sampled.sort(key=lambda e: e['span']['start'])

    review_entries = []
    for i, entry in enumerate(sampled, start=1):
        comm_start = entry['span']['start']
        comm_end = entry['span']['end']
        commentary_segment = commentary_text[comm_start:comm_end]

        root_segments = []
        for root_idx in entry['alignment_index']:
            span = target_index_to_span.get(root_idx)
            if span is None:
                root_segments.append({
                    'index': root_idx,
                    'span': None,
                    'root_text': None,
                    'error': 'index not found in target_annotation',
                })
                continue
            root_segments.append({
                'index': root_idx,
                'span': span,
                'root_text': root_text[span['start']:span['end']],
            })

        review_entries.append({
            'sample_number': i,
            'alignment_entry_index': entry['index'],
            'alignment_indices': entry['alignment_index'],
            'commentary_span': entry['span'],
            'commentary_text': commentary_segment,
            'root_segments': root_segments,
        })

    stem = commentary_path.stem
    output_path = output_dir / f'{stem}_alignment_review.json'
    review_doc = {
        'source_commentary': str(commentary_path),
        'source_alignment': str(alignment_path),
        'source_root': str(root_path),
        'n_sampled': n_segments,
        'seed': seed,
        'samples': review_entries,
    }
    write_json(output_path, review_doc)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Sample random alignment pairs from the alignment annotation and '
            'write a side-by-side review JSON.'
        ),
    )
    parser.add_argument(
        'commentary_file',
        type=Path,
        help='Path to the commentary output JSON (must have a base_content field).',
    )
    parser.add_argument(
        'n_segments',
        type=int,
        help='Number of random alignment segments to sample.',
    )
    parser.add_argument(
        '--alignment-path',
        type=Path,
        default=DEFAULT_ALIGNMENT_PATH,
        help=f'Alignment JSON. Defaults to {DEFAULT_ALIGNMENT_PATH}',
    )
    parser.add_argument(
        '--root-path',
        type=Path,
        default=DEFAULT_ROOT_PATH,
        help=f'Root annotation JSON (must have a content field). Defaults to {DEFAULT_ROOT_PATH}',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=DEFAULT_REVIEW_DIR,
        help=f'Directory to write the review JSON. Defaults to {DEFAULT_REVIEW_DIR}',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducible sampling.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = sample_alignments(
        args.commentary_file,
        args.n_segments,
        alignment_path=args.alignment_path,
        root_path=args.root_path,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    print(f'Review written to {output_path}')


if __name__ == '__main__':
    main()
