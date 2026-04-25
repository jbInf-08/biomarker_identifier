"""
Graph-augmented features and graph attention (GAT) for gene-expression matrices.

Uses a symmetric normalized adjacency (e.g., STRING high-confidence PPI) aligned
with ``X`` columns. The default ``ShallowGeneGCNClassifier`` name is kept for
API stability; the implementation is a **multi-head GAT** (replaces the former
shallow GCN) with layer normalization on node features.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


def symmetric_normalized_adjacency(A: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Symmetric normalized adjacency Ã = D^{-1/2} A D^{-1/2} (dense)."""
    A = np.asarray(A, dtype=np.float64)
    d = A.sum(axis=1)
    d_inv_sqrt = np.power(d + eps, -0.5)
    d_inv_sqrt[~np.isfinite(d_inv_sqrt)] = 0.0
    return (d_inv_sqrt[:, None] * A) * d_inv_sqrt[None, :]


def neighbor_mean_features(X: np.ndarray, A_norm: np.ndarray) -> np.ndarray:
    """Smooth each sample row with the normalized adjacency: X @ A_norm.T."""
    return np.asarray(X, dtype=np.float64) @ np.asarray(A_norm, dtype=np.float64).T


def augment_expression_with_graph(
    X: pd.DataFrame,
    gene_names: List[str],
    adjacency: np.ndarray,
    *,
    mode: str = "concat",
) -> pd.DataFrame:
    """
    Append or replace features with graph-smoothed expression.

    Parameters
    ----------
    X : samples x genes
    gene_names : order must match columns of X and rows/cols of adjacency
    adjacency : (G, G) non-negative
    mode : ``concat`` stacks [X | X_smooth], ``smooth_only`` returns smoothed only
    """
    cols = list(X.columns)
    if list(cols) != list(gene_names):
        raise ValueError("gene_names must match X.columns order exactly")
    A = np.asarray(adjacency)
    if A.shape[0] != A.shape[1] or A.shape[0] != len(gene_names):
        raise ValueError("adjacency must be square and match number of genes")
    A_n = symmetric_normalized_adjacency(A)
    Xm = X.values
    smooth = neighbor_mean_features(Xm, A_n)
    if mode == "concat":
        part = np.hstack([Xm, smooth])
        names = [str(g) for g in gene_names] + [f"{g}_nbr" for g in gene_names]
        return pd.DataFrame(part, index=X.index, columns=names)
    if mode == "smooth_only":
        return pd.DataFrame(
            smooth, index=X.index, columns=[f"{g}_sm" for g in gene_names]
        )
    raise ValueError("mode must be 'concat' or 'smooth_only'")


def adjacency_from_named_edges(
    gene_names: List[str],
    edges: List[Tuple[str, str, float]],
    *,
    self_loop: float = 1.0,
) -> np.ndarray:
    """
    Build a symmetric weighted adjacency from unordered gene–gene edges.

    Parameters
    ----------
    gene_names : genes in column order for ``X``
    edges : list of (gene_a, gene_b, weight)
    self_loop : diagonal value for numerical stability in GCN / smoothing
    """
    idx = {g: i for i, g in enumerate(gene_names)}
    n = len(gene_names)
    A = np.zeros((n, n), dtype=np.float64)
    for g1, g2, w in edges:
        if g1 not in idx or g2 not in idx:
            continue
        i, j = idx[g1], idx[g2]
        v = float(w)
        A[i, j] = max(A[i, j], v)
        A[j, i] = max(A[j, i], v)
    np.fill_diagonal(A, self_loop)
    return A


if TORCH_AVAILABLE:

    class _GATBlock(nn.Module):
        """One multi-head GAT layer (Veličković et al.) on a fixed support mask."""

        def __init__(
            self,
            in_dim: int,
            out_dim: int,
            n_heads: int,
            A_mask: torch.Tensor,
            dropout: float,
            negative_slope: float = 0.2,
        ):
            super().__init__()
            if out_dim % n_heads != 0:
                raise ValueError("out_dim must be divisible by n_heads")
            self.n_heads = n_heads
            self.d_head = out_dim // n_heads
            self.out_dim = out_dim
            self.register_buffer("A_mask", A_mask)
            self.W = nn.Linear(in_dim, out_dim, bias=False)
            self.a = nn.Parameter(torch.empty(n_heads, 2 * self.d_head))
            nn.init.xavier_uniform_(self.W.weight)
            nn.init.xavier_uniform_(self.a)
            self.leaky = nn.LeakyReLU(negative_slope)
            self.dropout = nn.Dropout(dropout)
            self.ln = nn.LayerNorm(out_dim)

        def forward(self, h: torch.Tensor) -> torch.Tensor:
            # h: (B, N, F_in)
            b, n, _ = h.shape
            n_h, d = self.n_heads, self.d_head
            wh = self.W(h).view(b, n, n_h, d)  # (B, N, H, d)
            a = self.a.view(n_h, 2, d)
            a_l, a_r = a[:, 0, :], a[:, 1, :]
            left = (wh * a_l.view(1, 1, n_h, d)).sum(-1)  # (B, N, H)
            right = (wh * a_r.view(1, 1, n_h, d)).sum(-1)
            e = self.leaky(left.unsqueeze(2) + right.unsqueeze(1))  # (B, N, N, H)
            e = e.permute(0, 3, 1, 2).contiguous()  # (B, H, N, N)
            m = (self.A_mask > 0).to(dtype=e.dtype)
            m = m.unsqueeze(0).unsqueeze(0).expand(b, n_h, n, n)
            e = e.masked_fill(m == 0, torch.finfo(e.dtype).min)
            att = torch.softmax(e, dim=-1)
            att = self.dropout(att)
            wh_t = wh.permute(0, 2, 1, 3)  # (B, H, N, d)
            out = torch.matmul(att, wh_t)  # (B, H, N, d)
            out = out.permute(0, 2, 1, 3).contiguous().view(b, n, n_h * d)
            return self.ln(out)

    class _GeneGATNet(nn.Module):
        """Two GAT blocks + mean pool + binary head (replaces former shallow GCN)."""

        def __init__(
            self,
            A_norm: torch.Tensor,
            hidden: int,
            dropout: float,
            n_heads: int = 4,
        ):
            super().__init__()
            a_max = A_norm.max()
            self.register_buffer("A", A_norm)
            self.register_buffer(
                "A_mask", (A_norm > (a_max * 1e-9)).to(dtype=torch.float32)
            )
            if hidden % n_heads != 0:
                raise ValueError("hidden must be divisible by n_heads")
            self.n_heads = n_heads
            self.gat1 = _GATBlock(1, hidden, n_heads, self.A_mask, dropout)
            self.gat2 = _GATBlock(hidden, hidden, n_heads, self.A_mask, dropout)
            self.drop = nn.Dropout(dropout)
            self.head = nn.Linear(hidden, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            h = x.unsqueeze(-1)
            h = self.gat1(h)
            h = torch.relu(h)
            h = self.drop(h)
            h = self.gat2(h)
            h = h.mean(dim=1)
            return self.head(h)

    class _DeepGeneGATNet(nn.Module):
        """Stacked GAT blocks (optional when ``ML_ENABLE_DEEP_GNN_STAGE`` is on)."""

        def __init__(
            self,
            A_norm: torch.Tensor,
            hidden: int,
            dropout: float,
            num_layers: int = 4,
            n_heads: int = 4,
        ):
            super().__init__()
            a_max = A_norm.max()
            self.register_buffer("A", A_norm)
            self.register_buffer(
                "A_mask", (A_norm > (a_max * 1e-9)).to(dtype=torch.float32)
            )
            self.num_layers = int(num_layers)
            if hidden % n_heads != 0:
                raise ValueError("hidden must be divisible by n_heads")
            self.n_heads = n_heads
            self.gat_in = _GATBlock(1, hidden, n_heads, self.A_mask, dropout)
            self.gat_stack = nn.ModuleList(
                [
                    _GATBlock(hidden, hidden, n_heads, self.A_mask, dropout)
                    for _ in range(self.num_layers)
                ]
            )
            self.drop = nn.Dropout(dropout)
            self.head = nn.Linear(hidden, 2)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            h = x.unsqueeze(-1)
            h = torch.relu(self.gat_in(h))
            for layer in self.gat_stack:
                h = torch.relu(layer(self.drop(h)))
            h = h.mean(dim=1)
            return self.head(h)


class ShallowGeneGCNClassifier:
    """
    Sklearn-style binary classifier: graph attention (GAT) on a fixed gene graph.

    Each sample is one graph snapshot: one scalar feature per gene (expression).
    (Class name kept for imports; the implementation is GAT, not GCN.)
    """

    def __init__(
        self,
        adjacency: np.ndarray,
        hidden: int = 64,
        dropout: float = 0.3,
        max_epochs: int = 120,
        batch_size: int = 32,
        learning_rate: float = 1e-3,
        patience: int = 15,
        random_state: int = 42,
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for ShallowGeneGCNClassifier")
        self.adjacency = np.asarray(adjacency, dtype=np.float64)
        self.A_norm = symmetric_normalized_adjacency(self.adjacency).astype(np.float32)
        self.hidden = hidden
        self.dropout = dropout
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.patience = patience
        self.random_state = random_state
        self.net_: Optional["_GeneGATNet"] = None
        self.classes_: Optional[np.ndarray] = None
        self.n_genes_: Optional[int] = None
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]):
        X_arr = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        y_arr = np.asarray(y).ravel()
        if X_arr.ndim != 2:
            raise ValueError("X must be 2D (samples x genes)")
        self.n_genes_ = X_arr.shape[1]
        if self.A_norm.shape[0] != self.n_genes_:
            raise ValueError(
                f"adjacency ({self.A_norm.shape[0]}) must match X columns ({self.n_genes_})"
            )
        self.classes_ = np.unique(y_arr)
        if len(self.classes_) != 2:
            raise ValueError("ShallowGeneGCNClassifier supports binary labels only")
        y_bin = (y_arr == self.classes_[1]).astype(np.int64)

        torch.manual_seed(self.random_state)
        A_t = torch.tensor(self.A_norm, device=self._device)
        self.net_ = _GeneGATNet(A_t, self.hidden, self.dropout).to(self._device)

        Xt = torch.tensor(X_arr, dtype=torch.float32, device=self._device)
        yt = torch.tensor(y_bin, dtype=torch.long, device=self._device)
        ds = TensorDataset(Xt, yt)
        loader = DataLoader(ds, batch_size=self.batch_size, shuffle=True)
        opt = torch.optim.Adam(self.net_.parameters(), lr=self.learning_rate)
        crit = nn.CrossEntropyLoss()
        best = float("inf")
        wait = 0
        for epoch in range(self.max_epochs):
            self.net_.train()
            ep = 0.0
            for xb, yb in loader:
                opt.zero_grad()
                logits = self.net_(xb)
                loss = crit(logits, yb)
                loss.backward()
                opt.step()
                ep += float(loss.item())
            ep /= max(len(loader), 1)
            if ep < best - 1e-6:
                best = ep
                wait = 0
            else:
                wait += 1
            if wait >= self.patience:
                logger.debug("GAT early stop epoch %s", epoch + 1)
                break
        return self

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        if self.net_ is None:
            raise ValueError("Call fit() first")
        X_arr = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        self.net_.eval()
        Xt = torch.tensor(X_arr, dtype=torch.float32, device=self._device)
        with torch.no_grad():
            logits = self.net_(Xt)
            p = torch.softmax(logits, dim=1).cpu().numpy()
        return p

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        p = self.predict_proba(X)[:, 1]
        pred = (p >= 0.5).astype(int)
        return np.where(pred == 1, self.classes_[1], self.classes_[0])


class DeepGeneGCNClassifier(ShallowGeneGCNClassifier):
    """
    Deeper GAT stack on a fixed gene graph (when ``ML_ENABLE_DEEP_GNN_STAGE`` is on).

    Same interface as ``ShallowGeneGCNClassifier``; uses more attention layers.
    """

    def __init__(
        self,
        adjacency: np.ndarray,
        *,
        num_gcn_layers: int = 4,
        hidden: int = 96,
        hidden_scale: int = 1,
        **kwargs: Any,
    ):
        del hidden_scale
        self._num_gcn_layers = num_gcn_layers
        super().__init__(adjacency, hidden=hidden, **kwargs)

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]):
        X_arr = X.values if isinstance(X, pd.DataFrame) else np.asarray(X)
        y_arr = np.asarray(y).ravel()
        if X_arr.ndim != 2:
            raise ValueError("X must be 2D (samples x genes)")
        self.n_genes_ = X_arr.shape[1]
        if self.A_norm.shape[0] != self.n_genes_:
            raise ValueError(
                f"adjacency ({self.A_norm.shape[0]}) must match X columns ({self.n_genes_})"
            )
        self.classes_ = np.unique(y_arr)
        if len(self.classes_) != 2:
            raise ValueError("DeepGeneGCNClassifier supports binary labels only")
        y_bin = (y_arr == self.classes_[1]).astype(np.int64)

        torch.manual_seed(self.random_state)
        A_t = torch.tensor(self.A_norm, device=self._device)
        self.net_ = _DeepGeneGATNet(
            A_t,
            self.hidden,
            self.dropout,
            num_layers=self._num_gcn_layers,
        ).to(self._device)

        Xt = torch.tensor(X_arr, dtype=torch.float32, device=self._device)
        yt = torch.tensor(y_bin, dtype=torch.long, device=self._device)
        ds = TensorDataset(Xt, yt)
        loader = DataLoader(ds, batch_size=self.batch_size, shuffle=True)
        opt = torch.optim.Adam(self.net_.parameters(), lr=self.learning_rate)
        crit = nn.CrossEntropyLoss()
        best = float("inf")
        wait = 0
        for epoch in range(self.max_epochs):
            self.net_.train()
            ep = 0.0
            for xb, yb in loader:
                opt.zero_grad()
                logits = self.net_(xb)
                loss = crit(logits, yb)
                loss.backward()
                opt.step()
                ep += float(loss.item())
            ep /= max(len(loader), 1)
            if ep < best - 1e-6:
                best = ep
                wait = 0
            else:
                wait += 1
            if wait >= self.patience:
                logger.debug("Deep GAT early stop epoch %s", epoch + 1)
                break
        return self


# Public aliases: the implementation is multi-head GAT (STRING-normalized),
# replacing the former shallow GCN. The legacy class names are preserved for
# backward-compatible imports across the rest of the codebase.
ShallowGeneGATClassifier = ShallowGeneGCNClassifier
DeepGeneGATClassifier = DeepGeneGCNClassifier
