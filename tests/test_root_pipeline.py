import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from cst_db_to_webuddhist_api.roots.root_pipline import (
    build_annotation_doc,
    build_root_doc,
    extract_segment_id,
    generate_metadata,
    make_heading,
    parse_segments,
    process_file,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _seg(css_class, content, chapter=0):
    return {'css_class': css_class, 'content': content, 'chapter': chapter}


def _input_data(segments, title_pali='Test Title'):
    return {'title_pali': title_pali, 'segments': segments}


# ---------------------------------------------------------------------------
# make_heading
# ---------------------------------------------------------------------------

class TestMakeHeading:
    def test_nikaya_produces_h1(self):
        assert make_heading('nikaya', 'Khuddaka') == '<h1>Khuddaka</h1>'

    def test_book_produces_h1(self):
        assert make_heading('book', 'Dhammapada') == '<h1>Dhammapada</h1>'

    def test_title_produces_h1(self):
        assert make_heading('title', 'Intro') == '<h1>Intro</h1>'

    def test_subhead_produces_h2(self):
        assert make_heading('subhead', 'Section A') == '<h2>Section A</h2>'

    def test_subsubhead_produces_h2(self):
        assert make_heading('subsubhead', 'Sub A') == '<h2>Sub A</h2>'

    def test_chapter_produces_h3(self):
        assert make_heading('chapter', '1. Yamakavaggo') == '<h3>1. Yamakavaggo</h3>'

    def test_unknown_class_falls_through_to_h3(self):
        assert make_heading('other', 'Misc') == '<h3>Misc</h3>'


# ---------------------------------------------------------------------------
# extract_segment_id
# ---------------------------------------------------------------------------

class TestExtractSegmentId:
    def test_extracts_leading_integer(self):
        assert extract_segment_id('42. Some content') == 42

    def test_extracts_single_digit(self):
        assert extract_segment_id('1. First') == 1

    def test_returns_none_for_non_numbered_content(self):
        assert extract_segment_id('No number here') is None

    def test_returns_none_for_empty_string(self):
        assert extract_segment_id('') is None

    def test_ignores_trailing_number_without_leading(self):
        assert extract_segment_id('Text 42.') is None


# ---------------------------------------------------------------------------
# parse_segments
# ---------------------------------------------------------------------------

class TestParseSegments:
    def test_heading_classes_produce_h1_h2_h3(self):
        segs = [
            _seg('nikaya', 'Khuddaka'),
            _seg('subhead', 'Section'),
            _seg('chapter', 'Chapter 1'),
        ]
        result = parse_segments(segs)
        assert result[0]['seg-content'] == '<h1>Khuddaka</h1>'
        assert result[1]['seg-content'] == '<h2>Section</h2>'
        assert result[2]['seg-content'] == '<h3>Chapter 1</h3>'

    def test_numbered_bodytext_starts_new_group_and_strips_number(self):
        segs = [_seg('bodytext', '1. First verse')]
        result = parse_segments(segs)
        assert result[0]['seg-content'] == 'First verse'
        assert result[0]['segment_id'] == 1

    def test_unnumbered_bodytext_appended_to_current_group_with_separator(self):
        segs = [
            _seg('bodytext', '1. First line'),
            _seg('bodytext', 'Second line'),
        ]
        result = parse_segments(segs)
        assert len(result) == 1
        assert result[0]['seg-content'] == 'First line ⤵ Second line'
        assert result[0]['segment_id'] == 1

    def test_unnumbered_bodytext_before_any_group_is_standalone(self):
        segs = [_seg('bodytext', 'Intro text')]
        result = parse_segments(segs)
        assert result[0]['seg-content'] == 'Intro text'
        assert result[0]['segment_id'] is None

    def test_new_numbered_bodytext_flushes_previous_group(self):
        segs = [
            _seg('bodytext', '1. First'),
            _seg('bodytext', '2. Second'),
        ]
        result = parse_segments(segs)
        assert len(result) == 2
        assert result[0]['seg-content'] == 'First'
        assert result[0]['segment_id'] == 1
        assert result[1]['seg-content'] == 'Second'
        assert result[1]['segment_id'] == 2

    def test_heading_flushes_open_group(self):
        segs = [
            _seg('bodytext', '1. Verse'),
            _seg('chapter', 'New Chapter'),
        ]
        result = parse_segments(segs)
        assert result[0]['seg-content'] == 'Verse'
        assert result[1]['seg-content'] == '<h3>New Chapter</h3>'

    def test_non_bodytext_non_heading_is_standalone(self):
        segs = [_seg('centered', 'Centered text')]
        result = parse_segments(segs)
        assert result[0]['seg-content'] == 'Centered text'
        assert result[0]['segment_id'] is None

    def test_chapter_number_preserved_in_output(self):
        segs = [_seg('bodytext', '5. Verse', chapter=2)]
        result = parse_segments(segs)
        assert result[0]['chapter'] == 2

    def test_empty_input_returns_empty_list(self):
        assert parse_segments([]) == []

    def test_multiple_continuation_lines_joined_in_order(self):
        segs = [
            _seg('bodytext', '1. Line A'),
            _seg('bodytext', 'Line B'),
            _seg('bodytext', 'Line C'),
        ]
        result = parse_segments(segs)
        assert len(result) == 1
        assert result[0]['seg-content'] == 'Line A ⤵ Line B ⤵ Line C'


# ---------------------------------------------------------------------------
# generate_metadata
# ---------------------------------------------------------------------------

class TestGenerateMetadata:
    def test_type_is_root(self):
        data = _input_data([], title_pali='Dhammapada')
        assert generate_metadata(data, 'pi-roman')['type'] == 'root'

    def test_title_uses_title_pali_for_both_en_and_bo(self):
        data = _input_data([], title_pali='Dhammapada')
        meta = generate_metadata(data, 'pi-roman')
        assert meta['title'] == {'en': 'Dhammapada', 'bo': 'Dhammapada'}

    def test_language_is_passed_through(self):
        data = _input_data([], title_pali='X')
        assert generate_metadata(data, 'pi-roman')['language'] == 'pi-roman'

    def test_copyright_and_license_defaults(self):
        data = _input_data([], title_pali='X')
        meta = generate_metadata(data, 'pi-roman')
        assert meta['copyright'] == 'Public domain'
        assert meta['license'] == 'CC0'

    def test_contributions_contains_one_author_entry(self):
        data = _input_data([], title_pali='X')
        contribs = generate_metadata(data, 'pi-roman')['contributions']
        assert len(contribs) == 1
        assert contribs[0]['role'] == 'author'


# ---------------------------------------------------------------------------
# build_root_doc
# ---------------------------------------------------------------------------

class TestBuildRootDoc:
    def test_content_is_space_joined_seg_contents(self):
        data = _input_data([
            _seg('nikaya', 'Khuddaka'),
            _seg('bodytext', '1. Verse one'),
        ])
        doc = build_root_doc(data, 'pi-roman')
        assert doc['content'] == '<h1>Khuddaka</h1> Verse one'

    def test_metadata_fields_present(self):
        data = _input_data([_seg('bodytext', '1. Verse')], title_pali='MyTitle')
        doc = build_root_doc(data, 'pi-roman')
        assert doc['type'] == 'root'
        assert doc['title'] == {'en': 'MyTitle', 'bo': 'MyTitle'}
        assert doc['language'] == 'pi-roman'

    def test_segments_list_present(self):
        data = _input_data([_seg('bodytext', '1. Verse')])
        doc = build_root_doc(data, 'pi-roman')
        assert isinstance(doc['segments'], list)
        assert len(doc['segments']) == 1


# ---------------------------------------------------------------------------
# build_annotation_doc
# ---------------------------------------------------------------------------

class TestBuildAnnotationDoc:
    def _root_doc(self, seg_contents):
        segments = [{'seg-content': s, 'segment_id': None, 'chapter': 0} for s in seg_contents]
        content = ' '.join(seg_contents)
        return {'segments': segments, 'content': content}

    def test_annotation_count_matches_segment_count(self):
        doc = self._root_doc(['Hello', 'World'])
        result = build_annotation_doc(doc)
        assert len(result['annotation']) == len(doc['segments'])

    def test_first_span_starts_at_zero(self):
        doc = self._root_doc(['Hello', 'World'])
        result = build_annotation_doc(doc)
        assert result['annotation'][0]['span']['start'] == 0

    def test_last_span_ends_at_last_character(self):
        doc = self._root_doc(['Hello', 'World'])
        result = build_annotation_doc(doc)
        assert result['annotation'][-1]['span']['end'] == len(doc['content']) - 1

    def test_spans_are_contiguous(self):
        doc = self._root_doc(['Alpha', 'Beta', 'Gamma'])
        result = build_annotation_doc(doc)
        anns = result['annotation']
        for i in range(len(anns) - 1):
            assert anns[i]['span']['end'] + 1 == anns[i + 1]['span']['start']

    def test_content_matches_root_doc_content(self):
        doc = self._root_doc(['One', 'Two'])
        result = build_annotation_doc(doc)
        assert result['content'] == doc['content']

    def test_metadata_type_is_critical(self):
        doc = self._root_doc(['One'])
        assert build_annotation_doc(doc)['metadata']['type'] == 'critical'

    def test_metadata_source_defaults_to_tipitaka(self):
        doc = self._root_doc(['One'])
        assert build_annotation_doc(doc)['metadata']['source'] == 'https://tipitaka.app/'

    def test_segment_id_preserved_in_annotation(self):
        segments = [{'seg-content': 'Verse', 'segment_id': 7, 'chapter': 0}]
        doc = {'segments': segments, 'content': 'Verse'}
        result = build_annotation_doc(doc)
        assert result['annotation'][0]['segment_id'] == 7

    def test_single_segment_span_covers_full_content(self):
        doc = self._root_doc(['Only segment'])
        result = build_annotation_doc(doc)
        ann = result['annotation'][0]
        assert ann['span']['start'] == 0
        assert ann['span']['end'] == len('Only segment') - 1


# ---------------------------------------------------------------------------
# process_file (I/O round-trip)
# ---------------------------------------------------------------------------

class TestProcessFile:
    def test_writes_root_and_annotation_json(self, tmp_path):
        input_path = tmp_path / 'input.json'
        root_out = tmp_path / 'root.json'
        annotation_out = tmp_path / 'annotation.json'

        input_path.write_text(json.dumps(_input_data([
            _seg('nikaya', 'Khuddaka'),
            _seg('bodytext', '1. Verse one'),
        ])), encoding='utf-8')

        process_file(input_path, root_out, annotation_out, lang='pi-roman')

        assert root_out.exists()
        assert annotation_out.exists()

    def test_root_output_is_valid_json_with_segments(self, tmp_path):
        input_path = tmp_path / 'input.json'
        root_out = tmp_path / 'root.json'
        annotation_out = tmp_path / 'annotation.json'

        input_path.write_text(json.dumps(_input_data([
            _seg('bodytext', '1. Verse'),
        ])), encoding='utf-8')

        process_file(input_path, root_out, annotation_out, lang='pi-roman')

        root = json.loads(root_out.read_text(encoding='utf-8'))
        assert root['type'] == 'root'
        assert isinstance(root['segments'], list)
        assert root['content'] != ''

    def test_annotation_output_spans_match_root_content(self, tmp_path):
        input_path = tmp_path / 'input.json'
        root_out = tmp_path / 'root.json'
        annotation_out = tmp_path / 'annotation.json'

        input_path.write_text(json.dumps(_input_data([
            _seg('bodytext', '1. Verse one'),
            _seg('bodytext', 'Continuation'),
        ])), encoding='utf-8')

        process_file(input_path, root_out, annotation_out, lang='pi-roman')

        root = json.loads(root_out.read_text(encoding='utf-8'))
        ann_doc = json.loads(annotation_out.read_text(encoding='utf-8'))
        content = ann_doc['content']

        for ann in ann_doc['annotation']:
            start = ann['span']['start']
            end = ann['span']['end']
            assert 0 <= start <= end < len(content)

    def test_creates_parent_directories(self, tmp_path):
        input_path = tmp_path / 'input.json'
        root_out = tmp_path / 'nested' / 'deep' / 'root.json'
        annotation_out = tmp_path / 'nested' / 'deep' / 'annotation.json'

        input_path.write_text(json.dumps(_input_data([_seg('bodytext', '1. Verse')])), encoding='utf-8')

        process_file(input_path, root_out, annotation_out, lang='pi-roman')
        assert root_out.exists()
        assert annotation_out.exists()
