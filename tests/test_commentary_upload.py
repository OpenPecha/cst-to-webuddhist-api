import json
import sys
from io import BytesIO
from pathlib import Path
from urllib import error

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from cst_db_to_webuddhist_api.commentary_upload import (
    build_commentary_payload,
    parse_header_args,
    post_commentary_payload,
    write_upload_payload,
)

TEST_PERSON_ID = 'test_person_id'
TEST_CATEGORY_ID = 'test_category_id'


def _processed_data():
    return {
        'language': 'pi-roman',
        'title': 'Test Commentary',
        'source': 'Test source',
        'base_content': 'First line\nSecond line',
        'annotations': [
            {
                'span': {'start': 0, 'end': 10},
                'segment_id': [],
            },
            {
                'span': {'start': 11, 'end': 22},
                'segment_id': [1],
            },
        ],
    }


def test_build_commentary_payload_maps_processed_output():
    payload = build_commentary_payload(
        _processed_data(),
        person_id=TEST_PERSON_ID,
        category_id=TEST_CATEGORY_ID,
    )

    assert payload['language'] == 'pi-roman'
    assert payload['content'] == 'First line\nSecond line'
    assert payload['title'] == 'Test Commentary'
    assert payload['source'] == 'Test source'
    assert payload['author'] == {'person_id': TEST_PERSON_ID}
    assert payload['category_id'] == TEST_CATEGORY_ID
    assert payload['copyright'] == 'Public domain'
    assert payload['license'] == 'CC0'
    assert payload['segmentation'] == [
        {'span': {'start': 0, 'end': 10}},
        {'span': {'start': 11, 'end': 22}},
    ]


def test_build_commentary_payload_omits_root_text_id():
    payload = build_commentary_payload(
        _processed_data(),
        person_id=TEST_PERSON_ID,
        category_id=TEST_CATEGORY_ID,
    )

    assert 'root_text_id' not in payload


def test_write_upload_payload_writes_payload_json(tmp_path):
    input_path = tmp_path / 'processed.json'
    output_path = tmp_path / 'upload' / 'payload.json'
    input_path.write_text(json.dumps(_processed_data()), encoding='utf-8')

    payload = write_upload_payload(
        input_path,
        output_path,
        person_id=TEST_PERSON_ID,
        category_id=TEST_CATEGORY_ID,
    )

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding='utf-8')) == payload


def test_parse_header_args_parses_multiple_headers():
    headers = parse_header_args(['Authorization: Bearer token', 'X-Client: cst-uploader'])

    assert headers == {
        'Authorization': 'Bearer token',
        'X-Client': 'cst-uploader',
    }


def test_parse_header_args_rejects_invalid_format():
    with pytest.raises(ValueError, match='Expected format'):
        parse_header_args(['Authorization Bearer token'])


def test_post_commentary_payload_posts_json(monkeypatch):
    payload = build_commentary_payload(
        _processed_data(),
        person_id=TEST_PERSON_ID,
        category_id=TEST_CATEGORY_ID,
    )
    observed: dict[str, object] = {}

    class _Response:
        def __init__(self, body: str):
            self._body = body.encode('utf-8')

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    def _fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        observed['url'] = req.full_url
        observed['method'] = req.get_method()
        observed['content_type'] = req.headers.get('Content-type')
        observed['auth'] = req.headers.get('Authorization')
        observed['body'] = req.data.decode('utf-8') if req.data else ''
        observed['timeout'] = timeout
        return _Response('{"ok": true}')

    monkeypatch.setattr('cst_db_to_webuddhist_api.commentary_upload.request.urlopen', _fake_urlopen)

    response = post_commentary_payload(
        'instance123',
        payload,
        base_url='https://example.org/',
        headers={'Authorization': 'Bearer abc'},
        timeout=15,
    )

    assert observed['url'] == 'https://example.org/v2/instances/instance123/commentary'
    assert observed['method'] == 'POST'
    assert observed['content_type'] == 'application/json'
    assert observed['auth'] == 'Bearer abc'
    assert observed['timeout'] == 15
    assert json.loads(observed['body']) == payload
    assert response == {'ok': True}


def test_post_commentary_payload_raises_with_api_error_body(monkeypatch):
    payload = build_commentary_payload(
        _processed_data(),
        person_id=TEST_PERSON_ID,
        category_id=TEST_CATEGORY_ID,
    )

    def _fake_urlopen(req, timeout):  # type: ignore[no-untyped-def]
        raise error.HTTPError(
            req.full_url,
            400,
            'Bad Request',
            hdrs=None,
            fp=BytesIO(b'{"message":"invalid category"}'),
        )

    monkeypatch.setattr('cst_db_to_webuddhist_api.commentary_upload.request.urlopen', _fake_urlopen)

    with pytest.raises(RuntimeError, match='HTTP 400'):
        post_commentary_payload('instance123', payload, base_url='https://example.org/')
