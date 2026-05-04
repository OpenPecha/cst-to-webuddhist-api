import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'cst-db-to-webuddhist-api'))
from validate_commentary_root_segments import (  # noqa: E402
    count_segment_runs,
    validate_segment_count,
)


def _ann(segment_id):
    return {'span': {'start': 0, 'end': 1}, 'segment_id': segment_id}


def test_count_segment_runs_collapses_consecutive_scalar_ids():
    annotations = [_ann(1), _ann(1), _ann(2), _ann(1)]

    assert count_segment_runs(annotations, 1) == 2


def test_count_segment_runs_collapses_consecutive_matching_list_ids():
    annotations = [_ann([1]), _ann([1]), _ann([1, 2]), _ann([1, 2])]

    assert count_segment_runs(annotations, 1) == 1
    assert count_segment_runs(annotations, 2) == 1


def test_empty_segment_ids_break_consecutive_runs():
    annotations = [_ann([1]), _ann([]), _ann([1])]

    assert count_segment_runs(annotations, 1) == 2


def test_validate_segment_count_matches_equal_counts():
    root = [_ann(1), _ann(2), _ann(1)]
    commentary = [_ann([1]), _ann([2]), _ann([1])]

    result = validate_segment_count(commentary, root, 1)

    assert result.matches
    assert result.commentary_count == 2
    assert result.root_count == 2


def test_validate_segment_count_reports_different_counts():
    root = [_ann(1)]
    commentary = [_ann([1]), _ann([2]), _ann([1])]

    result = validate_segment_count(commentary, root, 1)

    assert not result.matches
    assert result.segment_id == 1
    assert result.commentary_count == 2
    assert result.root_count == 1
