<<<<<<< HEAD
=======
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from cst_db_to_webuddhist_api.commentary_pipeline import (
    calculate_spans,
    extract_id,
    generate_metadata,
    parse_segments,
)


def _make_seg(content, css_class='bodytext', chapter=0):
    return {'content': content, 'css_class': css_class, 'chapter': chapter}


def test_span_roundtrip():
    raw = [
        _make_seg('Namo tassa', 'centered'),
        _make_seg('1. First numbered', 'bodytext'),
        _make_seg('continuation', 'bodytext'),
        _make_seg('2. Second numbered', 'bodytext'),
    ]
    parsed = parse_segments(raw)
    result = calculate_spans(parsed)
    base = result['base_content']
    for ann in result['annotations']:
        start, end = ann['span']['start'], ann['span']['end']
        assert base[start:end] == next(s['content'] for s in parsed
                                       if s['content'] == base[start:end])


def test_segment_ids():
    raw = [
        _make_seg('Heading', 'nikaya', chapter=0),
        _make_seg('1. First', 'bodytext', chapter=1),
        _make_seg('still first', 'bodytext', chapter=1),
        _make_seg('2. Second', 'bodytext', chapter=1),
    ]
    parsed = parse_segments(raw)
    ids = [s['segment_id'] for s in parsed]
    assert ids == [[], [1], [1], [2]]


def test_heading_resets_segment_id():
    raw = [
        _make_seg('1. Para one', 'bodytext', chapter=0),
        _make_seg('Chapter heading', 'chapter', chapter=1),
        _make_seg('orphan', 'bodytext', chapter=1),
    ]
    parsed = parse_segments(raw)
    assert parsed[0]['segment_id'] == [1]
    assert parsed[1]['segment_id'] == []
    assert parsed[2]['segment_id'] == []


def test_gatha_inherits_segment_id():
    raw = [
        _make_seg('1. Before gatha', 'bodytext', chapter=0),
        _make_seg('Gatha line', 'gatha1', chapter=0),
    ]
    parsed = parse_segments(raw)
    assert parsed[1]['segment_id'] == [1]


def test_number_not_stripped_of_trailing_space():
    raw = [_make_seg('1. Some text here', 'bodytext', chapter=0)]
    parsed = parse_segments(raw)
    assert parsed[0]['content'] == ' Some text here'


def test_duplicate_segment_ids_are_preserved_without_chapter():
    raw = [
        _make_seg('1. Mātikā section', 'bodytext', chapter=2),
        _make_seg('1. Kaṇḍa section', 'bodytext', chapter=4),
    ]
    parsed = parse_segments(raw)
    assert parsed[0]['segment_id'] == parsed[1]['segment_id'] == [1]


def test_segment_id_ranges_expand_to_lists():
    raw = [
        _make_seg('1-6. Range section', 'bodytext', chapter=2),
        _make_seg('range continuation', 'bodytext', chapter=2),
    ]
    parsed = parse_segments(raw)
    assert parsed[0]['segment_id'] == [1, 2, 3, 4, 5, 6]
    assert parsed[1]['segment_id'] == [1, 2, 3, 4, 5, 6]


def test_spans_are_ordered_and_non_overlapping():
    raw = [
        _make_seg('Namo tassa', 'centered', chapter=0),
        _make_seg('1. First', 'bodytext', chapter=1),
        _make_seg('second line', 'bodytext', chapter=1),
    ]
    parsed = parse_segments(raw)
    result = calculate_spans(parsed)
    anns = result['annotations']
    for i in range(len(anns) - 1):
        assert anns[i]['span']['end'] < anns[i + 1]['span']['start']


def test_metadata_layer_titles():
    for layer, expected_suffix in [
        ('atthakatha', 'Commentary'),
        ('tika', 'Primary Sub-commentary'),
        ('other', 'Secondary Sub-commentary'),
    ]:
        data = {'layer': layer, 'title_pali': 'TestText'}
        meta = generate_metadata(data, language='pi-roman')
        assert expected_suffix in meta['title']
        assert meta['language'] == 'pi-roman'
        assert 'tipitaka.app' in meta['source']


def test_extract_id_range():
    assert extract_id('1-6. Some range text') == 1
    assert extract_id('135. Single') == 135
>>>>>>> 5773c1bba97c51568101b1963576a04477053ac7
