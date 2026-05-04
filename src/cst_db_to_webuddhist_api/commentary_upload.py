import argparse
import json
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_API_BASE_URL = 'https://api-aq25662yyq-uc.a.run.app/'
DEFAULT_COPYRIGHT = 'Public domain'
DEFAULT_LICENSE = 'CC0'

DEFAULT_INPUT_PATH = Path('data/output/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json')
DEFAULT_UPLOAD_PATH = Path('data/upload/Dhammasaṅgaṇīpāḷi/Dhammasaṅgaṇi-aṭṭhakathā.json')


def build_commentary_payload(
    processed_data: dict[str, Any],
    *,
    person_id: str,
    category_id: str,
    copyright: str = DEFAULT_COPYRIGHT,
    license: str = DEFAULT_LICENSE,
) -> dict[str, Any]:
    return {
        'language': processed_data['language'],
        'content': processed_data['base_content'],
        'title': processed_data['title'],
        'source': processed_data['source'],
        'author': {
            'person_id': person_id,
        },
        'segmentation': [
            {
                'span': annotation['span'],
            }
            for annotation in processed_data['annotations']
        ],
        'copyright': copyright,
        'license': license,
        'category_id': category_id,
    }


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def write_upload_payload(
    input_path: Path,
    output_path: Path,
    *,
    person_id: str,
    category_id: str,
    copyright: str = DEFAULT_COPYRIGHT,
    license: str = DEFAULT_LICENSE,
) -> dict[str, Any]:
    processed_data = load_json(input_path)
    payload = build_commentary_payload(
        processed_data,
        person_id=person_id,
        category_id=category_id,
        copyright=copyright,
        license=license,
    )
    write_json(output_path, payload)
    return payload


def parse_header_args(header_args: list[str] | None) -> dict[str, str]:
    if not header_args:
        return {}

    headers: dict[str, str] = {}
    for header in header_args:
        if ':' not in header:
            raise ValueError(f'Invalid header "{header}". Expected format: "Key: Value".')
        key, value = header.split(':', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f'Invalid header "{header}". Header name cannot be empty.')
        headers[key] = value
    return headers


def post_commentary_payload(
    instance_id: str,
    payload: dict[str, Any],
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    url = f'{base_url.rstrip("/")}/v2/instances/{instance_id}/commentary'
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            **(headers or {}),
        },
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            response_body = response.read().decode('utf-8')
    except error.HTTPError as exc:
        error_body = exc.read().decode('utf-8', errors='replace').strip()
        detail = error_body or str(exc.reason)
        raise RuntimeError(
            f'POST {url} failed with HTTP {exc.code}: {detail}',
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            f'POST {url} failed: {exc.reason}',
        ) from exc

    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return {'raw_response': response_body}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Build WebBuddhist commentary upload JSON from processed CST output.',
    )
    parser.add_argument(
        'input_path',
        nargs='?',
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f'Processed commentary JSON path. Defaults to {DEFAULT_INPUT_PATH}',
    )
    parser.add_argument(
        'output_path',
        nargs='?',
        type=Path,
        default=DEFAULT_UPLOAD_PATH,
        help=f'Upload payload JSON path. Defaults to {DEFAULT_UPLOAD_PATH}',
    )
    parser.add_argument('--person-id', required=True, help='Author person_id for the upload payload.')
    parser.add_argument('--category-id', required=True, help='Category ID for the upload payload.')
    parser.add_argument('--copyright', default=DEFAULT_COPYRIGHT)
    parser.add_argument('--license', default=DEFAULT_LICENSE)
    parser.add_argument(
        '--post',
        action='store_true',
        help='POST the generated payload to the API.',
    )
    parser.add_argument(
        '--instance-id',
        help='WebBuddhist instance id used in POST URL.',
    )
    parser.add_argument(
        '--api-base-url',
        default=DEFAULT_API_BASE_URL,
        help=f'API base URL. Defaults to {DEFAULT_API_BASE_URL}',
    )
    parser.add_argument(
        '--header',
        dest='headers',
        action='append',
        default=None,
        help='HTTP header in "Key: Value" format. Repeat for multiple headers.',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='HTTP timeout in seconds for upload POST.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = write_upload_payload(
        args.input_path,
        args.output_path,
        person_id=args.person_id,
        category_id=args.category_id,
        copyright=args.copyright,
        license=args.license,
    )
    print(f'Wrote {args.output_path} ({len(payload["segmentation"])} segments)')

    if args.post:
        if not args.instance_id:
            raise ValueError('--instance-id is required when --post is used.')
        headers = parse_header_args(args.headers)
        response_data = post_commentary_payload(
            args.instance_id,
            payload,
            base_url=args.api_base_url,
            headers=headers,
            timeout=args.timeout,
        )
        print(
            f'Uploaded commentary to {args.api_base_url.rstrip("/")}/v2/instances/{args.instance_id}/commentary',
        )
        if response_data:
            print(json.dumps(response_data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
