import argparse
import json
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_API_BASE_URL = 'https://api-aq25662yyq-uc.a.run.app/'
DEFAULT_COPYRIGHT = 'Public domain'
DEFAULT_LICENSE = 'CC0'


def build_text_payload(root_doc: dict[str, Any]) -> dict[str, Any]:
    return {
        'type': root_doc['type'],
        'title': root_doc['title'],
        'language': root_doc['language'],
        'contributions': root_doc['contributions'],
        'category_id': root_doc.get('category_id'),
        'copyright': root_doc.get('copyright', DEFAULT_COPYRIGHT),
        'license': root_doc.get('license', DEFAULT_LICENSE),
    }


def build_instance_payload(annotation_doc: dict[str, Any]) -> dict[str, Any]:
    return {
        'metadata': annotation_doc['metadata'],
        'annotation': [{'span': entry['span']} for entry in annotation_doc.get('annotation', [])],
        'content': annotation_doc['content'],
    }


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _post(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json', **headers},
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            response_body = response.read().decode('utf-8')
    except error.HTTPError as exc:
        error_body = exc.read().decode('utf-8', errors='replace').strip()
        detail = error_body or str(exc.reason)
        raise RuntimeError(f'POST {url} failed with HTTP {exc.code}: {detail}') from exc
    except error.URLError as exc:
        raise RuntimeError(f'POST {url} failed: {exc.reason}') from exc

    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return {'raw_response': response_body}


def post_text(
    payload: dict[str, Any],
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    timeout: int = 30,
) -> str:
    url = f'{base_url.rstrip("/")}/v2/texts'
    response = _post(url, payload, headers={}, timeout=timeout)
    text_id = response.get('id')
    if not text_id:
        raise RuntimeError(f'POST {url} succeeded but response contains no "id": {response}')
    return text_id


def post_instance(
    text_id: str,
    payload: dict[str, Any],
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    timeout: int = 30,
) -> dict[str, Any]:
    url = f'{base_url.rstrip("/")}/v2/texts/{text_id}/instances'
    return _post(url, payload, headers={}, timeout=timeout)


def upload_annotation_file(
    annotation_path: Path,
    *,
    base_url: str,
    timeout: int,
) -> None:
    stem = annotation_path.stem.removesuffix('_annotation')
    root_path = annotation_path.parent / f'{stem}.json'

    if not root_path.exists():
        print(f'Skipping {annotation_path.name}: root JSON not found at {root_path}')
        return

    text_payload = build_text_payload(load_json(root_path))
    instance_payload = build_instance_payload(load_json(annotation_path))

    text_id = post_text(text_payload, base_url=base_url, timeout=timeout)
    print(f'Created text {text_id} from {root_path.name}')

    response = post_instance(text_id, instance_payload, base_url=base_url, timeout=timeout)
    instance_id = response.get('id', '<unknown>')
    print(f'Created instance {instance_id} for text {text_id} from {annotation_path.name}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Upload root texts and critical instances to the WebBuddhist API.',
    )
    parser.add_argument(
        'folder_name',
        help="Sub-folder under data/output/root/, e.g. 'Dhammapadapāḷi'.",
    )
    parser.add_argument(
        '--post',
        action='store_true',
        help='POST the payloads to the API.',
    )
    parser.add_argument(
        '--api-base-url',
        default=DEFAULT_API_BASE_URL,
        help=f'API base URL. Defaults to {DEFAULT_API_BASE_URL}',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='HTTP timeout in seconds (default: 30).',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).parents[3]
    folder = repo_root / 'data' / 'output' / 'root' / args.folder_name

    if not folder.exists():
        raise SystemExit(f'Folder not found: {folder}')

    annotation_files = sorted(folder.glob('*_annotation.json'))
    if not annotation_files:
        raise SystemExit(f'No *_annotation.json files found in {folder}')

    print(f'Found {len(annotation_files)} annotation file(s) in {folder}')

    if not args.post:
        print('Use --post to upload to the API.')
        return

    for annotation_path in annotation_files:
        upload_annotation_file(
            annotation_path,
            base_url=args.api_base_url,
            timeout=args.timeout,
        )


if __name__ == '__main__':
    main()
