import json
import sys


def matches_segment_id(annotation: dict, segment_id: int) -> bool:
    annotation_segment_id = annotation['segment_id']
    if isinstance(annotation_segment_id, list):
        return segment_id in annotation_segment_id
    return annotation_segment_id == segment_id


def group_consecutive_annotations(annotations: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for annotation in sorted(annotations, key=lambda a: a['span']['start']):
        if not groups:
            groups.append([annotation])
            continue

        previous = groups[-1][-1]
        previous_end = previous['span']['end']
        current_start = annotation['span']['start']
        if current_start <= previous_end + 1:
            groups[-1].append(annotation)
        else:
            groups.append([annotation])

    return groups


def test_segment(json_path: str, segment_id: int, chapter: int | None = None) -> None:
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    base = data['base_content']
    matches = [a for a in data['annotations']
               if matches_segment_id(a, segment_id)
               and (chapter is None or a.get('chapter') == chapter)]

    if not matches:
        label = f'segment_id={segment_id}' + (f', chapter={chapter}' if chapter is not None else '')
        print(f'No annotations found for {label}')
        return

    label = f'segment_id={segment_id}, chapter={chapter}' if chapter is not None else f'segment_id={segment_id}'
    groups = group_consecutive_annotations(matches)
    print(f'{label}  ({len(matches)} segment(s), {len(groups)} block(s))\n')
    for i, group in enumerate(groups):
        start = group[0]['span']['start']
        end = group[-1]['span']['end']
        text = base[start:end]
        print(f'[{i}] span=({start}, {end}) segment_count={len(group)}')
        print('```')
        print(text)
        print('```')
        print()


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        print('Usage: python segment_tester.py <output_json> <segment_id> [chapter]')
        sys.exit(1)
    chapter = int(sys.argv[3]) if len(sys.argv) == 4 else None
    test_segment(sys.argv[1], int(sys.argv[2]), chapter)
