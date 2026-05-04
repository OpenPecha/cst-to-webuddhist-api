import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'cst-db-to-webuddhist-api'))
from alignment_pipeline import (  # noqa: E402
    assign_indices,
    build_alignment,
    merge_consecutive,
    write_alignment,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ann(start, end, sid, chapter=0):
    return {'span': {'start': start, 'end': end}, 'segment_id': sid, 'chapter': chapter}


def _root_data(annotations):
    return {'annotation': annotations, 'content': ''}


def _comm_data(annotations):
    return {'annotations': annotations, 'base_content': ''}


# ---------------------------------------------------------------------------
# merge_consecutive
# ---------------------------------------------------------------------------

class TestMergeConsecutive:
    def test_collapses_contiguous_same_integer_sid(self):
        anns = [_ann(0, 10, 1), _ann(11, 20, 1), _ann(21, 30, 1)]
        result = merge_consecutive(anns)
        assert len(result) == 1
        assert result[0]['span'] == {'start': 0, 'end': 30}
        assert result[0]['segment_ids'] == (1,)

    def test_keeps_non_contiguous_same_sid_separate(self):
        anns = [_ann(0, 10, 1), _ann(12, 20, 1)]
        result = merge_consecutive(anns)
        assert len(result) == 2
        assert result[0]['span'] == {'start': 0, 'end': 10}
        assert result[1]['span'] == {'start': 12, 'end': 20}

    def test_keeps_repeated_sid_with_different_sid_between_separate(self):
        anns = [_ann(0, 10, 1), _ann(11, 20, 2), _ann(21, 30, 1)]
        result = merge_consecutive(anns)
        assert len(result) == 3
        assert result[0]['span'] == {'start': 0, 'end': 10}
        assert result[2]['span'] == {'start': 21, 'end': 30}

    def test_collapses_contiguous_same_sid_list(self):
        anns = [_ann(0, 10, [1, 2]), _ann(11, 20, [1, 2])]
        result = merge_consecutive(anns)
        assert len(result) == 1
        assert result[0]['span'] == {'start': 0, 'end': 20}
        assert result[0]['segment_ids'] == (1, 2)

    def test_unaligned_entries_are_atomic_and_not_merged_with_neighbours(self):
        anns = [_ann(0, 10, None), _ann(11, 20, None), _ann(21, 30, 1)]
        result = merge_consecutive(anns)
        assert len(result) == 3
        assert result[0]['segment_ids'] == ()
        assert result[1]['segment_ids'] == ()
        assert result[2]['segment_ids'] == (1,)

    def test_empty_sid_lists_are_unaligned(self):
        anns = [_ann(0, 10, []), _ann(11, 20, [1])]
        result = merge_consecutive(anns)
        assert result[0]['segment_ids'] == ()
        assert result[1]['segment_ids'] == (1,)

    def test_empty_input(self):
        assert merge_consecutive([]) == []

    def test_span_start_is_first_end_is_last(self):
        anns = [_ann(5, 10, 3), _ann(11, 15, 3), _ann(16, 25, 3)]
        result = merge_consecutive(anns)
        assert result[0]['span']['start'] == 5
        assert result[0]['span']['end'] == 25

    def test_mixed_runs(self):
        anns = [
            _ann(0, 5, 1), _ann(6, 10, 1),
            _ann(11, 20, 2),
            _ann(21, 30, 3), _ann(31, 40, 3), _ann(41, 50, 3),
        ]
        result = merge_consecutive(anns)
        assert len(result) == 3
        assert result[0]['span'] == {'start': 0, 'end': 10}
        assert result[1]['span'] == {'start': 11, 'end': 20}
        assert result[2]['span'] == {'start': 21, 'end': 50}


# ---------------------------------------------------------------------------
# assign_indices — sequential integer output indices
# ---------------------------------------------------------------------------

class TestAssignIndices:
    def test_single_occurrence_gets_zero_index(self):
        merged = [{'span': {'start': 0, 'end': 10}, 'segment_ids': (5,)}]
        result = assign_indices(merged)
        assert result[0]['index'] == 0
        assert isinstance(result[0]['index'], int)

    def test_repeated_segment_ids_get_sequential_indices(self):
        merged = [
            {'span': {'start': 0, 'end': 10}, 'segment_ids': (1,)},
            {'span': {'start': 11, 'end': 20}, 'segment_ids': (1,)},
        ]
        result = assign_indices(merged)
        assert [entry['index'] for entry in result] == [0, 1]

    def test_unaligned_entries_are_dropped(self):
        merged = [
            {'span': {'start': 0, 'end': 10}, 'segment_ids': ()},
            {'span': {'start': 11, 'end': 20}, 'segment_ids': (3,)},
        ]
        result = assign_indices(merged)
        assert len(result) == 1
        assert result[0]['index'] == 0

    def test_output_entries_carry_span_segment_ids_index(self):
        merged = [{'span': {'start': 0, 'end': 10}, 'segment_ids': (7,)}]
        result = assign_indices(merged)
        assert set(result[0].keys()) == {'span', 'segment_ids', 'index'}

    def test_empty_input(self):
        assert assign_indices([]) == []

    def test_indices_are_all_integers(self):
        merged = [
            {'span': {'start': 0, 'end': 10}, 'segment_ids': (1,)},
            {'span': {'start': 11, 'end': 20}, 'segment_ids': (500,)},
        ]
        result = assign_indices(merged)
        for entry in result:
            assert isinstance(entry['index'], int)

    def test_all_indices_unique(self):
        # Build a variety of entries and verify no collisions.
        merged = [
            {'span': {'start': i * 10, 'end': i * 10 + 9}, 'segment_ids': segment_ids}
            for i, segment_ids in enumerate([(1,), (2,), (1,), (1, 2), (1,)])
        ]
        result = assign_indices(merged)
        indices = [e['index'] for e in result]
        assert len(indices) == len(set(indices))


# ---------------------------------------------------------------------------
# build_alignment
# ---------------------------------------------------------------------------

class TestBuildAlignment:
    def test_basic_one_to_one_match(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([_ann(200, 300, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert result['type'] == 'alignment'
        assert result['target_manifestation_id'] == 'MNF001'
        assert len(result['target_annotation']) == 1
        assert len(result['alignment_annotation']) == 1
        assert result['target_annotation'][0] == {
            'span': {'start': 0, 'end': 100},
            'index': 0,
        }
        assert result['alignment_annotation'][0] == {
            'span': {'start': 200, 'end': 300},
            'index': 0,
            'alignment_index': [0],
        }

    def test_indices_are_integers_in_output(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([_ann(200, 300, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert isinstance(result['target_annotation'][0]['index'], int)
        assert isinstance(result['alignment_annotation'][0]['index'], int)
        assert isinstance(result['alignment_annotation'][0]['alignment_index'][0], int)

    def test_commentary_empty_sid_list_dropped(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([_ann(0, 50, []), _ann(200, 300, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert len(result['alignment_annotation']) == 1
        assert result['alignment_annotation'][0]['index'] == 0

    def test_unreferenced_root_annotations_dropped(self):
        root = _root_data([_ann(0, 100, 1, chapter=0), _ann(101, 200, 2, chapter=0)])
        comm = _comm_data([_ann(300, 400, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        indices = [t['index'] for t in result['target_annotation']]
        assert indices == [0]
        assert result['target_annotation'][0]['span'] == {'start': 0, 'end': 100}

    def test_repeated_sid_maps_by_occurrence_instead_of_all_matches(self):
        root = _root_data([
            _ann(0, 10, 1, chapter=0),
            _ann(11, 20, 2, chapter=0),
            _ann(21, 30, 1, chapter=0),
        ])
        comm = _comm_data([
            _ann(200, 300, [1], chapter=3),
            _ann(302, 400, [1], chapter=3),
        ])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert result['target_annotation'] == [
            {'span': {'start': 0, 'end': 10}, 'index': 0},
            {'span': {'start': 21, 'end': 30}, 'index': 1},
        ]
        assert result['alignment_annotation'] == [
            {'span': {'start': 200, 'end': 300}, 'index': 0, 'alignment_index': [0]},
            {'span': {'start': 302, 'end': 400}, 'index': 1, 'alignment_index': [1]},
        ]

    def test_commentary_with_no_root_match_dropped(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([_ann(200, 300, [99], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert result['alignment_annotation'] == []
        assert result['target_annotation'] == []

    def test_consecutive_commentary_segments_merged_before_indexing(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([
            _ann(200, 250, [1], chapter=2),
            _ann(251, 300, [1], chapter=2),
            _ann(301, 350, [1], chapter=2),
        ])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert len(result['alignment_annotation']) == 1
        assert result['alignment_annotation'][0]['span'] == {'start': 200, 'end': 350}

    def test_consecutive_root_segments_merged_before_pairing(self):
        root = _root_data([
            _ann(0, 100, 1, chapter=0),
            _ann(101, 200, 1, chapter=0),
        ])
        comm = _comm_data([_ann(300, 400, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert result['target_annotation'] == [
            {'span': {'start': 0, 'end': 200}, 'index': 0},
        ]
        assert result['alignment_annotation'][0]['alignment_index'] == [0]

    def test_multi_id_commentary_maps_each_id_by_matching_occurrence(self):
        root = _root_data([
            _ann(0, 10, 1),
            _ann(11, 20, 2),
            _ann(21, 30, 1),
            _ann(31, 40, 2),
        ])
        comm = _comm_data([
            _ann(100, 110, [1, 2]),
            _ann(112, 120, [1, 2]),
        ])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert result['target_annotation'] == [
            {'span': {'start': 0, 'end': 10}, 'index': 0},
            {'span': {'start': 11, 'end': 20}, 'index': 1},
            {'span': {'start': 21, 'end': 30}, 'index': 2},
            {'span': {'start': 31, 'end': 40}, 'index': 3},
        ]
        assert result['alignment_annotation'] == [
            {'span': {'start': 100, 'end': 110}, 'index': 0, 'alignment_index': [0, 1]},
            {'span': {'start': 112, 'end': 120}, 'index': 1, 'alignment_index': [2, 3]},
        ]

    def test_output_target_entries_have_only_span_and_index(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([_ann(200, 300, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert set(result['target_annotation'][0].keys()) == {'span', 'index'}

    def test_output_alignment_entries_have_span_index_alignment_index(self):
        root = _root_data([_ann(0, 100, 1, chapter=0)])
        comm = _comm_data([_ann(200, 300, [1], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert set(result['alignment_annotation'][0].keys()) == {'span', 'index', 'alignment_index'}

    def test_multiple_commentary_sids_each_get_own_entry(self):
        root = _root_data([_ann(0, 50, 1, chapter=0), _ann(51, 100, 2, chapter=0)])
        comm = _comm_data([_ann(200, 250, [1], chapter=2), _ann(251, 300, [2], chapter=2)])
        result = build_alignment(root, comm, target_manifestation_id='MNF001')

        assert len(result['target_annotation']) == 2
        assert len(result['alignment_annotation']) == 2


# ---------------------------------------------------------------------------
# write_alignment (file round-trip)
# ---------------------------------------------------------------------------

class TestWriteAlignment:
    def test_round_trip_writes_valid_json(self, tmp_path):
        root_path = tmp_path / 'root.json'
        comm_path = tmp_path / 'commentary.json'
        out_path = tmp_path / 'alignment.json'

        root_path.write_text(
            json.dumps(_root_data([_ann(0, 100, 1, chapter=0)])), encoding='utf-8'
        )
        comm_path.write_text(
            json.dumps(_comm_data([_ann(200, 300, 1, chapter=2)])), encoding='utf-8'
        )

        result = write_alignment(root_path, comm_path, out_path, target_manifestation_id='MNFTEST')

        loaded = json.loads(out_path.read_text(encoding='utf-8'))
        assert loaded == result
        assert loaded['target_manifestation_id'] == 'MNFTEST'
        assert len(loaded['target_annotation']) == 1
        assert len(loaded['alignment_annotation']) == 1
        assert isinstance(loaded['target_annotation'][0]['index'], int)

    def test_creates_parent_directories(self, tmp_path):
        root_path = tmp_path / 'root.json'
        comm_path = tmp_path / 'commentary.json'
        out_path = tmp_path / 'nested' / 'deep' / 'alignment.json'

        root_path.write_text(json.dumps(_root_data([_ann(0, 10, 1, chapter=0)])), encoding='utf-8')
        comm_path.write_text(json.dumps(_comm_data([_ann(20, 30, 1, chapter=2)])), encoding='utf-8')

        write_alignment(root_path, comm_path, out_path, target_manifestation_id='MNFTEST')
        assert out_path.exists()
