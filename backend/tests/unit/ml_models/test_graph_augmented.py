"""Graph augmentation and adjacency helpers."""

import numpy as np
import pandas as pd
import pytest

from app.ml_models.graph_augmented import (
    adjacency_from_named_edges,
    augment_expression_with_graph,
    symmetric_normalized_adjacency,
)


def test_adjacency_and_augment_concat():
    genes = ["A", "B", "C"]
    X = pd.DataFrame([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], columns=genes)
    edges = [("A", "B", 0.9), ("B", "C", 0.5)]
    A = adjacency_from_named_edges(genes, edges, self_loop=1.0)
    assert A.shape == (3, 3)
    out = augment_expression_with_graph(X, genes, A, mode="concat")
    assert out.shape == (2, 6)


def test_symmetric_norm():
    A = np.array([[1.0, 1.0], [1.0, 1.0]])
    An = symmetric_normalized_adjacency(A)
    assert An.shape == (2, 2)


def _has_torch() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_torch(), reason="torch not installed")
def test_shallow_gcn_fit_predict():
    from app.ml_models.graph_augmented import ShallowGeneGATClassifier, ShallowGeneGCNClassifier

    assert ShallowGeneGATClassifier is ShallowGeneGCNClassifier
    rng = np.random.default_rng(42)
    G = 12
    A = rng.random((G, G))
    A = (A + A.T) / 2
    np.fill_diagonal(A, 1.0)
    X = rng.normal(size=(40, G))
    y = (rng.random(40) > 0.55).astype(int)
    clf = ShallowGeneGATClassifier(adjacency=A, max_epochs=5, patience=2, random_state=0)
    clf.fit(pd.DataFrame(X), pd.Series(y))
    p = clf.predict_proba(pd.DataFrame(X))
    assert p.shape == (40, 2)
