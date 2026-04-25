"""
Deep Learning Models for Biomarker Discovery.

This module provides PyTorch-based deep learning classifiers for tabular biomarker data,
with sklearn-compatible wrappers for integration into the ML pipeline.
"""

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True

    class TabularBiomarkerNet(nn.Module):
        """
        PyTorch MLP for tabular biomarker classification.
        Supports configurable depth and width.
        """

        def __init__(
            self,
            input_dim: int,
            num_classes: int = 2,
            hidden_dims: Tuple[int, ...] = (256, 128, 64),
            dropout: float = 0.3,
        ):
            super().__init__()
            self.input_dim = input_dim
            self.num_classes = num_classes
            self.hidden_dims = hidden_dims
            layers = []
            prev = input_dim
            for h in hidden_dims:
                layers.append(nn.Linear(prev, h))
                layers.append(nn.BatchNorm1d(h))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout))
                prev = h
            self.backbone = nn.Sequential(*layers)
            self.head = nn.Linear(prev, num_classes)

        def forward(self, x):
            x = self.backbone(x)
            return self.head(x)

except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    TabularBiomarkerNet = None  # type: ignore


def _get_device():
    """Get best available device."""
    if not TORCH_AVAILABLE:
        return None
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class PyTorchTabularClassifier(BaseEstimator, ClassifierMixin):
    """
    Sklearn-compatible wrapper for PyTorch tabular classifier.
    Implements fit, predict, predict_proba, get_params, set_params for pipeline integration.
    """

    def __init__(
        self,
        hidden_dims: Tuple[int, ...] = (256, 128, 64),
        dropout: float = 0.3,
        max_epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 1e-3,
        patience: int = 10,
        random_state: int = 42,
        device: Optional[str] = None,
        use_focal_loss: bool = False,
        focal_gamma: float = 2.0,
        focal_alpha: Optional[float] = None,
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is required. Install with: pip install torch")
        self.hidden_dims = hidden_dims
        self.dropout = dropout
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.patience = patience
        self.random_state = random_state
        self.device = device or str(_get_device())
        self.use_focal_loss = use_focal_loss
        self.focal_gamma = focal_gamma
        self.focal_alpha = focal_alpha
        self.net_ = None
        self.input_dim_ = None
        self.classes_ = None
        self._fitted = False

    def get_params(self, deep: bool = True) -> Dict[str, Any]:
        return {
            "hidden_dims": self.hidden_dims,
            "dropout": self.dropout,
            "max_epochs": self.max_epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "patience": self.patience,
            "random_state": self.random_state,
            "device": self.device,
            "use_focal_loss": self.use_focal_loss,
            "focal_gamma": self.focal_gamma,
            "focal_alpha": self.focal_alpha,
        }

    def set_params(self, **params) -> "PyTorchTabularClassifier":
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
        return self

    def _to_tensor(
        self, X: Union[np.ndarray, pd.DataFrame], y: Optional[np.ndarray] = None
    ):
        if isinstance(X, pd.DataFrame):
            X = X.values.astype(np.float32)
        else:
            X = np.asarray(X, dtype=np.float32)
        X = torch.from_numpy(X)
        if y is not None:
            y = np.asarray(y)
            if len(np.unique(y)) == 2 and (y.min() != 0 or y.max() != 1):
                from sklearn.preprocessing import LabelEncoder

                le = LabelEncoder()
                y = le.fit_transform(y)
            y = torch.from_numpy(y).long()
            return X, y
        return X

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]):
        """Train the deep learning model."""
        X_arr = np.asarray(X) if not isinstance(X, pd.DataFrame) else X.values
        y_arr = np.asarray(y).ravel()
        self.classes_ = np.unique(y_arr)
        n_classes = len(self.classes_)
        self.input_dim_ = X_arr.shape[1]

        if n_classes != 2:
            logger.warning(
                "Deep classifier implemented for binary classification; mapping to binary for training."
            )

        # Map to 0/1 if needed
        if n_classes == 2:
            y_binary = (y_arr == self.classes_[1]).astype(np.int64)
        else:
            # Multi-class: use first class vs rest for compatibility with predict_proba[:, 1]
            y_binary = (y_arr != self.classes_[0]).astype(np.int64)
            n_classes = 2

        self.net_ = TabularBiomarkerNet(
            input_dim=self.input_dim_,
            num_classes=2,
            hidden_dims=self.hidden_dims,
            dropout=self.dropout,
        )
        device = torch.device(self.device)
        self.net_.to(device)

        if self.random_state is not None:
            torch.manual_seed(self.random_state)
            if torch.cuda.is_available():
                torch.cuda.manual_seed(self.random_state)

        X_t, y_t = self._to_tensor(X_arr, y_binary)
        dataset = TensorDataset(X_t, y_t)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        optimizer = torch.optim.Adam(self.net_.parameters(), lr=self.learning_rate)
        ce = nn.CrossEntropyLoss(reduction="none")

        n_pos = float((y_binary == 1).sum())
        n_neg = float((y_binary == 0).sum())
        if self.focal_alpha is not None:
            alpha_pos = self.focal_alpha
        else:
            alpha_pos = n_neg / max(n_pos + n_neg, 1.0)

        def focal_loss(logits: "torch.Tensor", targets: "torch.Tensor") -> "torch.Tensor":
            p_t = torch.softmax(logits, dim=1).gather(
                1, targets.unsqueeze(1)
            ).squeeze(1)
            ce_n = ce(logits, targets)
            focal = (1 - p_t) ** self.focal_gamma * ce_n
            w = torch.where(
                targets == 1,
                torch.tensor(alpha_pos, device=logits.device, dtype=logits.dtype),
                torch.tensor(1.0 - alpha_pos, device=logits.device, dtype=logits.dtype),
            )
            return (w * focal).mean()

        best_loss = float("inf")
        wait = 0

        for epoch in range(self.max_epochs):
            self.net_.train()
            epoch_loss = 0.0
            for batch_x, batch_y in loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                optimizer.zero_grad()
                logits = self.net_(batch_x)
                if self.use_focal_loss:
                    loss = focal_loss(logits, batch_y)
                else:
                    loss = ce(logits, batch_y).mean()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            epoch_loss /= len(loader)

            if epoch_loss < best_loss:
                best_loss = epoch_loss
                wait = 0
            else:
                wait += 1
            if wait >= self.patience:
                logger.debug(f"Early stopping at epoch {epoch + 1}")
                break

        self._fitted = True
        return self

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class labels."""
        proba = self.predict_proba(X)
        pred_idx = (proba[:, 1] >= 0.5).astype(np.int64)
        return self.classes_[pred_idx]

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class probabilities. Returns (n_samples, 2) for binary."""
        if not self._fitted or self.net_ is None:
            raise ValueError("Model not fitted. Call fit first.")
        self.net_.eval()
        X_t = self._to_tensor(X)
        device = torch.device(self.device)
        X_t = X_t.to(device)
        with torch.no_grad():
            logits = self.net_(X_t)
            probs = torch.softmax(logits, dim=1).cpu().numpy()
        return probs


def get_deep_learning_wrapper(
    random_state: int = 42,
    hidden_dims: Tuple[int, ...] = (256, 128, 64),
    max_epochs: int = 80,
    batch_size: int = 32,
    use_focal_loss: bool = False,
    focal_gamma: float = 2.0,
    focal_alpha: Optional[float] = None,
) -> Optional[PyTorchTabularClassifier]:
    """Return an sklearn-compatible deep learning classifier if PyTorch is available."""
    if not TORCH_AVAILABLE:
        logger.warning("PyTorch not installed. Deep learning model skipped.")
        return None
    return PyTorchTabularClassifier(
        hidden_dims=hidden_dims,
        dropout=0.3,
        max_epochs=max_epochs,
        batch_size=batch_size,
        learning_rate=1e-3,
        patience=10,
        random_state=random_state,
        use_focal_loss=use_focal_loss,
        focal_gamma=focal_gamma,
        focal_alpha=focal_alpha,
    )
