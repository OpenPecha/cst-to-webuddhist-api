import argparse
import json
import re
from pathlib import Path

NUMBERED = re.compile(r'^\d{1,4}(-\d{1,4})?\.')
NUMBERED_RANGE = re.compile(r'^(\d{1,4})(?:-(\d{1,4}))?\.')
GATHA_CLASSES = {'gatha1', 'gatha2', 'gatha3', 'gathalast'}

H1_CLASSES = {'nikaya', 'book', 'title'}
H2_CLASSES = {'subsubhead', 'subhead'}
H3_CLASSES = {'chapter'}
HEADING_CLASSES = H1_CLASSES | H2_CLASSES | H3_CLASSES

BODY_CLASSES = {'bodytext', 'indent', 'unindented'}


def strip_number(content: str) -> str:
    return NUMBERED.sub('', content, count=1)


def make_heading(cls: str, content: str) -> str:
    text = strip_number(content)
    if cls in H1_CLASSES:
        return f'<h1>{text}</h1>'
    if cls in H2_CLASSES:
        return f'<h2>{text}</h2>'
    return f'<h3>{text}</h3>'


def extract_id(content: str) -> int:
    m = NUMBERED.match(content)
    return int(m.group(0).rstrip('.').split('-')[0])


def extract_id_list(content: str) -> list[int]:
    m = NUMBERED_RANGE.match(content)
    if not m:
        return []
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    if end < start:
        return [start]
    return list(range(start, end + 1))


def parse_segments(segments: list[dict]) -> list[dict]:
    result: list[dict] = []
    current_ids: list[int] = []

    for seg in segments:
        cls = seg['css_class']
        content = seg['content']

        if cls in HEADING_CLASSES:
            current_ids = []
            result.append({'content': make_heading(cls, content), 'segment_id': []})

        elif cls == 'centered':
            current_ids = []
            result.append({'content': content, 'segment_id': []})

        elif cls in GATHA_CLASSES:
            result.append({'content': content, 'segment_id': list(current_ids)})

        elif cls in BODY_CLASSES:
            if NUMBERED.match(content):
                current_ids = extract_id_list(content)
                result.append({'content': strip_number(content), 'segment_id': list(current_ids)})
            else:
                result.append({'content': content, 'segment_id': list(current_ids)})

    return result


LAYER_TITLES = {
    'atthakatha': '{title} (Commentary)',
    'tika':       '{title} (Primary Sub-commentary)',
    'other':      '{title} (Secondary Sub-commentary)',
}


def generate_metadata(data: dict, language: str) -> dict:
    layer = data.get('layer', 'other')
    title_pali = data['title_pali']
    title_tmpl = LAYER_TITLES.get(layer, '{title}')
    return {
        'language': language,
        'title': title_tmpl.format(title=title_pali),
        'source': 'Chaṭṭha Saṅgāyana Tipiṭaka (CST), https://tipitaka.app/',
    }


def calculate_spans(segments: list[dict]) -> dict:
    annotations = []
    pos = 0
    for seg in segments:
        content = seg['content']
        start = pos
        end = pos + len(content)
        annotations.append({
            'span': {'start': start, 'end': end},
            'segment_id': seg['segment_id'],
        })
        pos = end + 1  # +1 for the joining newline

    base_content = '\n'.join(seg['content'] for seg in segments)
    return {'base_content': base_content, 'annotations': annotations}


def process_file(json_path: Path, output_path: Path, language: str) -> None:
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    groups = parse_segments(data['segments'])
    result = {**generate_metadata(data, language), **calculate_spans(groups)}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'{json_path.name} → {output_path} ({len(groups)} segments)')


def run(input_dir: str, output_dir: str, language: str) -> None:
    data_path = Path(input_dir)
    output_path = Path(output_dir)

    json_files = list(data_path.rglob('*.json'))
    if not json_files:
        print(f'No JSON files found under {data_path}')
        return

    for json_file in json_files:
        relative = json_file.relative_to(data_path)
        out_file = output_path / relative.with_suffix('.json')
        process_file(json_file, out_file, language)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Convert CST JSON files into WebBuddha-ready annotation JSON.',
    )
    parser.add_argument(
        '--input-dir',
        default='data/input',
        help='Directory containing raw CST JSON files. Defaults to data/input',
    )
    parser.add_argument(
        '--output-dir',
        default='data/output',
        help='Directory to write processed output JSON. Defaults to data/output',
    )
    parser.add_argument(
        '--language',
        required=True,
        help='Language code for the output (e.g. pi-roman, pi-thai).',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    run(args.input_dir, args.output_dir, args.language)
