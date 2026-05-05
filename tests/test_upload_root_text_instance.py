import json
import sys
from io import BytesIO
from pathlib import Path
from urllib import error

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from cst_db_to_webuddhist_api.roots.upload_root_text_instance import (
    build_instance_payload,
    build_text_payload,
    post_instance,
    post_text,
    upload_annotation_file,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _root_doc(**kwargs):
    base = {
        'type': 'root',
        'title': {'en': 'Test Title', 'bo': 'Test Title'},
        'language': 'pi-roman',
        'contributions': [{'person_id': 'person123', 'role': 'author'}],
        'category_id': 'cat456',
        'copyright': 'Public domain',
        'license': 'CC0',
    }
    base.update(kwargs)
    return base


def _annotation_doc(**kwargs):
    base = {
        'metadata': {'type': 'critical', 'source': 'https://tipitaka.app/'},
        'annotation': [
            {'span': {'start': 0, 'end': 10}, 'segment_id': 1},
            {'span': {'start': 11, 'end': 20}, 'segment_id': 2},
        ],
        'content': 'Hello world',
    }
    base.update(kwargs)
    return base


class _Response:
    def __init__(self, body: str):
        self._body = body.encode('utf-8')

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


# ---------------------------------------------------------------------------
# build_text_payload
# ---------------------------------------------------------------------------

class TestBuildTextPayload:
    def test_maps_all_fields_from_root_doc(self):
        payload = build_text_payload(_root_doc())

        assert payload['type'] == 'root'
        assert payload['title'] == {'en': 'Test Title', 'bo': 'Test Title'}
        assert payload['language'] == 'pi-roman'
        assert payload['contributions'] == [{'person_id': 'person123', 'role': 'author'}]
        assert payload['category_id'] == 'cat456'
        assert payload['copyright'] == 'Public domain'
        assert payload['license'] == 'CC0'

    def test_category_id_is_none_when_absent(self):
        doc = _root_doc()
        doc.pop('category_id')
        assert build_text_payload(doc)['category_id'] is None

    def test_copyright_defaults_to_public_domain_when_absent(self):
        doc = _root_doc()
        doc.pop('copyright')
        assert build_text_payload(doc)['copyright'] == 'Public domain'

    def test_license_defaults_to_cc0_when_absent(self):
        doc = _root_doc()
        doc.pop('license')
        assert build_text_payload(doc)['license'] == 'CC0'


# ---------------------------------------------------------------------------
# build_instance_payload
# ---------------------------------------------------------------------------

class TestBuildInstancePayload:
    def test_metadata_passed_through(self):
        payload = build_instance_payload(_annotation_doc())
        assert payload['metadata'] == {'type': 'critical', 'source': 'https://tipitaka.app/'}

    def test_content_passed_through(self):
        payload = build_instance_payload(_annotation_doc())
        assert payload['content'] == 'Hello world'

    def test_annotation_contains_only_span(self):
        payload = build_instance_payload(_annotation_doc())
        for entry in payload['annotation']:
            assert set(entry.keys()) == {'span'}

    def test_segment_id_stripped_from_annotation(self):
        payload = build_instance_payload(_annotation_doc())
        for entry in payload['annotation']:
            assert 'segment_id' not in entry

    def test_span_values_preserved(self):
        payload = build_instance_payload(_annotation_doc())
        assert payload['annotation'][0]['span'] == {'start': 0, 'end': 10}
        assert payload['annotation'][1]['span'] == {'start': 11, 'end': 20}

    def test_empty_annotation_list(self):
        payload = build_instance_payload(_annotation_doc(annotation=[]))
        assert payload['annotation'] == []


# ---------------------------------------------------------------------------
# post_text
# ---------------------------------------------------------------------------

class TestPostText:
    def test_posts_to_correct_url(self, monkeypatch):
        observed = {}

        def _fake_urlopen(req, timeout):
            observed['url'] = req.full_url
            return _Response('{"id": "T123"}')

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        post_text(build_text_payload(_root_doc()), base_url='https://example.org/')

        assert observed['url'] == 'https://example.org/v2/texts'

    def test_returns_text_id_from_response(self, monkeypatch):
        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            lambda req, timeout: _Response('{"id": "T999"}'),
        )

        text_id = post_text(build_text_payload(_root_doc()), base_url='https://example.org/')

        assert text_id == 'T999'

    def test_sends_payload_as_json_body(self, monkeypatch):
        observed = {}

        def _fake_urlopen(req, timeout):
            observed['body'] = json.loads(req.data.decode('utf-8'))
            return _Response('{"id": "T1"}')

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        payload = build_text_payload(_root_doc())
        post_text(payload, base_url='https://example.org/')

        assert observed['body'] == payload

    def test_raises_when_response_has_no_id(self, monkeypatch):
        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            lambda req, timeout: _Response('{"message": "ok"}'),
        )

        with pytest.raises(RuntimeError, match='no "id"'):
            post_text(build_text_payload(_root_doc()), base_url='https://example.org/')

    def test_raises_on_http_error(self, monkeypatch):
        def _fake_urlopen(req, timeout):
            raise error.HTTPError(req.full_url, 422, 'Unprocessable', hdrs=None, fp=BytesIO(b'bad input'))

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        with pytest.raises(RuntimeError, match='HTTP 422'):
            post_text(build_text_payload(_root_doc()), base_url='https://example.org/')


# ---------------------------------------------------------------------------
# post_instance
# ---------------------------------------------------------------------------

class TestPostInstance:
    def test_posts_to_correct_url_with_text_id(self, monkeypatch):
        observed = {}

        def _fake_urlopen(req, timeout):
            observed['url'] = req.full_url
            return _Response('{"id": "I456"}')

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        post_instance('T123', build_instance_payload(_annotation_doc()), base_url='https://example.org/')

        assert observed['url'] == 'https://example.org/v2/texts/T123/instances'

    def test_returns_response_dict(self, monkeypatch):
        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            lambda req, timeout: _Response('{"id": "I456"}'),
        )

        response = post_instance('T123', build_instance_payload(_annotation_doc()), base_url='https://example.org/')

        assert response == {'id': 'I456'}

    def test_raises_on_http_error(self, monkeypatch):
        def _fake_urlopen(req, timeout):
            raise error.HTTPError(req.full_url, 400, 'Bad Request', hdrs=None, fp=BytesIO(b'error'))

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        with pytest.raises(RuntimeError, match='HTTP 400'):
            post_instance('T123', build_instance_payload(_annotation_doc()), base_url='https://example.org/')


# ---------------------------------------------------------------------------
# upload_annotation_file
# ---------------------------------------------------------------------------

class TestUploadAnnotationFile:
    def _write_pair(self, tmp_path, stem='s0502m'):
        root_path = tmp_path / f'{stem}.json'
        annotation_path = tmp_path / f'{stem}_annotation.json'
        root_path.write_text(json.dumps(_root_doc()), encoding='utf-8')
        annotation_path.write_text(json.dumps(_annotation_doc()), encoding='utf-8')
        return annotation_path

    def test_posts_text_then_instance_in_order(self, tmp_path, monkeypatch):
        annotation_path = self._write_pair(tmp_path)
        calls = []

        def _fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if '/v2/texts' in req.full_url and 'instances' not in req.full_url:
                return _Response('{"id": "T1"}')
            return _Response('{"id": "I1"}')

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        upload_annotation_file(annotation_path, base_url='https://example.org/', timeout=10)

        assert calls[0].endswith('/v2/texts')
        assert 'instances' in calls[1]

    def test_instance_url_uses_text_id_from_text_response(self, tmp_path, monkeypatch):
        annotation_path = self._write_pair(tmp_path)
        calls = []

        def _fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if 'instances' not in req.full_url:
                return _Response('{"id": "TEXTABC"}')
            return _Response('{"id": "INST1"}')

        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            _fake_urlopen,
        )

        upload_annotation_file(annotation_path, base_url='https://example.org/', timeout=10)

        assert 'TEXTABC' in calls[1]

    def test_skips_when_root_json_missing(self, tmp_path, monkeypatch, capsys):
        annotation_path = tmp_path / 's0502m_annotation.json'
        annotation_path.write_text(json.dumps(_annotation_doc()), encoding='utf-8')

        called = []
        monkeypatch.setattr(
            'cst_db_to_webuddhist_api.roots.upload_root_text_instance.request.urlopen',
            lambda req, timeout: called.append(req.full_url),
        )

        upload_annotation_file(annotation_path, base_url='https://example.org/', timeout=10)

        assert called == []
        assert 'Skipping' in capsys.readouterr().out
