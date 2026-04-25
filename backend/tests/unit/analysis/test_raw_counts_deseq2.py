import pandas as pd
import pytest

from app.analysis.raw_counts_deseq2 import _validate_raw_counts_inputs


def test_validate_raw_counts_inputs_requires_condition_replicates():
    counts = pd.DataFrame(
        {
            "s1": [10, 5],
            "s2": [11, 6],
            "s3": [8, 4],
            "s4": [9, 7],
        },
        index=["geneA", "geneB"],
    )
    coldata = pd.DataFrame(
        {"condition": ["A", "A", "B", "B"]},
        index=["s1", "s2", "s3", "s4"],
    )
    out_counts, out_col = _validate_raw_counts_inputs(counts, coldata)
    assert out_counts.shape == (2, 4)
    assert out_col.shape[0] == 4


def test_validate_raw_counts_inputs_rejects_negative_counts():
    counts = pd.DataFrame(
        {
            "s1": [10, -5],
            "s2": [11, 6],
            "s3": [8, 4],
            "s4": [9, 7],
        },
        index=["geneA", "geneB"],
    )
    coldata = pd.DataFrame(
        {"condition": ["A", "A", "B", "B"]},
        index=["s1", "s2", "s3", "s4"],
    )
    with pytest.raises(ValueError, match="negative"):
        _validate_raw_counts_inputs(counts, coldata)
