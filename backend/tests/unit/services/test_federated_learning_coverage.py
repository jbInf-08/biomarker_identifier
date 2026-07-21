"""
Self-contained unit tests for ``app.services.federated_learning_service``.

Runnable with ``--noconftest``: no project fixtures are used. Optional heavy
dependencies (``torch``, ``cryptography``) are stubbed into ``sys.modules``
ONLY when the real package is absent, so CI still exercises the real ones.
All database access is redirected to a private in-memory SQLite engine.
"""

import base64
import importlib.util
import os
import pickle
import sys
import types
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")


# ---------------------------------------------------------------------------
# Optional-dependency stubs (installed only when the real package is missing)
# ---------------------------------------------------------------------------
def _install_torch_stub() -> None:
    torch_mod = types.ModuleType("torch")
    nn_mod = types.ModuleType("torch.nn")

    class _T:
        """Minimal numpy-backed tensor stand-in."""

        def __init__(self, arr):
            self._a = np.asarray(arr)

        def numpy(self):
            return self._a

        @property
        def shape(self):
            return self._a.shape

    class _Param:
        def __init__(self, arr):
            self.data = _T(arr)

    def _tensor(data, dtype=None):
        if isinstance(data, _T):
            data = data._a
        return _T(np.asarray(data, dtype=np.float64))

    def _argmax(t, dim=None):
        a = t._a if isinstance(t, _T) else np.asarray(t)
        return _T(np.argmax(a, axis=dim))

    class _NoGrad:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Module:
        def __init__(self):
            object.__setattr__(self, "_stub_modules", {})
            object.__setattr__(self, "_stub_params", {})

        def __setattr__(self, name, value):
            if isinstance(value, Module):
                self._stub_modules[name] = value
            elif isinstance(value, _Param):
                self._stub_params[name] = value
            object.__setattr__(self, name, value)

        def named_parameters(self, prefix=""):
            for name, param in self._stub_params.items():
                yield prefix + name, param
            for mod_name, mod in self._stub_modules.items():
                yield from mod.named_parameters(prefix + mod_name + ".")

        def parameters(self):
            for _, param in self.named_parameters():
                yield param

        def load_state_dict(self, state_dict, strict=True):
            object.__setattr__(self, "_stub_loaded_state", dict(state_dict))
            return ([], [])

        def state_dict(self):
            return {name: p.data for name, p in self.named_parameters()}

        def eval(self):
            return self

        def train(self, mode=True):
            return self

        def forward(self, x):
            return x

        def __call__(self, *args, **kwargs):
            return self.forward(*args, **kwargs)

    class Linear(Module):
        def __init__(self, in_features, out_features, bias=True):
            super().__init__()
            rng = np.random.default_rng(0)
            self.in_features = in_features
            self.out_features = out_features
            self.weight = _Param(
                rng.standard_normal((out_features, in_features)) * 0.01
            )
            if bias:
                self.bias = _Param(np.zeros(out_features))

        def forward(self, x):
            arr = x._a if isinstance(x, _T) else np.asarray(x)
            out = arr @ self.weight.data.numpy().T
            if hasattr(self, "bias"):
                out = out + self.bias.data.numpy()
            return _T(out)

    class Dropout(Module):
        def __init__(self, p=0.5):
            super().__init__()
            self.p = p

    class ReLU(Module):
        def forward(self, x):
            arr = x._a if isinstance(x, _T) else np.asarray(x)
            return _T(np.maximum(arr, 0.0))

    nn_mod.Module = Module
    nn_mod.Linear = Linear
    nn_mod.Dropout = Dropout
    nn_mod.ReLU = ReLU
    nn_mod.Parameter = _Param

    torch_mod.nn = nn_mod
    torch_mod.Tensor = _T
    torch_mod.tensor = _tensor
    torch_mod.argmax = _argmax
    torch_mod.no_grad = _NoGrad
    torch_mod.float32 = "float32"
    torch_mod.float64 = "float64"

    sys.modules["torch"] = torch_mod
    sys.modules["torch.nn"] = nn_mod


def _install_cryptography_stub() -> None:
    import hashlib

    root = types.ModuleType("cryptography")
    fernet_mod = types.ModuleType("cryptography.fernet")
    hazmat = types.ModuleType("cryptography.hazmat")
    primitives = types.ModuleType("cryptography.hazmat.primitives")
    hashes_mod = types.ModuleType("cryptography.hazmat.primitives.hashes")
    kdf_mod = types.ModuleType("cryptography.hazmat.primitives.kdf")
    pbkdf2_mod = types.ModuleType("cryptography.hazmat.primitives.kdf.pbkdf2")

    class InvalidToken(Exception):
        pass

    class Fernet:
        _PREFIX = b"stubfernet:"

        def __init__(self, key):
            self.key = key

        def encrypt(self, data: bytes) -> bytes:
            return self._PREFIX + base64.urlsafe_b64encode(data)

        def decrypt(self, token: bytes) -> bytes:
            if not token.startswith(self._PREFIX):
                raise InvalidToken("bad token")
            return base64.urlsafe_b64decode(token[len(self._PREFIX) :])

    class SHA256:
        name = "sha256"

    class PBKDF2HMAC:
        def __init__(self, algorithm=None, length=32, salt=b"", iterations=1000):
            self.length = length
            self.salt = salt
            self.iterations = iterations

        def derive(self, password: bytes) -> bytes:
            return hashlib.pbkdf2_hmac(
                "sha256", password, self.salt, self.iterations, dklen=self.length
            )

    fernet_mod.Fernet = Fernet
    fernet_mod.InvalidToken = InvalidToken
    hashes_mod.SHA256 = SHA256
    pbkdf2_mod.PBKDF2HMAC = PBKDF2HMAC

    root.fernet = fernet_mod
    root.hazmat = hazmat
    hazmat.primitives = primitives
    primitives.hashes = hashes_mod
    primitives.kdf = kdf_mod
    kdf_mod.pbkdf2 = pbkdf2_mod

    sys.modules["cryptography"] = root
    sys.modules["cryptography.fernet"] = fernet_mod
    sys.modules["cryptography.hazmat"] = hazmat
    sys.modules["cryptography.hazmat.primitives"] = primitives
    sys.modules["cryptography.hazmat.primitives.hashes"] = hashes_mod
    sys.modules["cryptography.hazmat.primitives.kdf"] = kdf_mod
    sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = pbkdf2_mod


HAS_REAL_TORCH = importlib.util.find_spec("torch") is not None
if not HAS_REAL_TORCH:
    _install_torch_stub()
if importlib.util.find_spec("cryptography") is None:
    _install_cryptography_stub()


import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402

# Import sibling model modules so SQLAlchemy can resolve cross-model
# relationship names (e.g. AnalysisRun -> User) when mappers configure.
from app.models import run_model as _run_model  # noqa: E402,F401
from app.models import tenant_model as _tenant_model  # noqa: E402,F401
from app.models import user_model as _user_model  # noqa: E402,F401
from app.models.federated import (  # noqa: E402
    FederatedGlobalModel,
    FederatedModel,
    FederatedParticipant,
    FederatedRound,
)
from app.models.platform_models import FederatedIdempotency  # noqa: E402
from app.services import federated_learning_service as fls  # noqa: E402

FederatedConfig = fls.FederatedConfig
FederatedLearningService = fls.FederatedLearningService
ModelUpdate = fls.ModelUpdate


# ---------------------------------------------------------------------------
# Fixtures (all local to this file)
# ---------------------------------------------------------------------------
_TABLES = [
    FederatedParticipant.__table__,
    FederatedRound.__table__,
    FederatedModel.__table__,
    FederatedGlobalModel.__table__,
    FederatedIdempotency.__table__,
]


@pytest.fixture
def session_factory(monkeypatch):
    """Redirect the service's ``db_session`` to a private in-memory SQLite DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    Local = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @contextmanager
    def _db_session():
        db = Local()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(fls, "db_session", _db_session)
    yield Local
    engine.dispose()


@pytest.fixture
def service():
    return FederatedLearningService()


def _weights(scale: float, seed: int = 0):
    rng = np.random.default_rng(seed)
    return {
        "layer1": rng.standard_normal((4, 3)) * 0 + scale,
        "bias1": np.full(3, scale),
    }


def _insert_update(
    svc,
    Local,
    round_id,
    participant_id,
    weights,
    num_samples,
    loss=0.5,
    accuracy=0.8,
    meta_data=None,
):
    db = Local()
    try:
        row = FederatedModel(
            participant_id=participant_id,
            round_id=round_id,
            model_weights=svc._encrypt_data(weights),
            num_samples=num_samples,
            loss=loss,
            accuracy=accuracy,
            submitted_at=datetime.now(),
            is_aggregated=False,
            meta_data=meta_data,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dataclasses / construction
# ---------------------------------------------------------------------------
def test_federated_config_defaults():
    cfg = FederatedConfig()
    assert cfg.num_rounds == 10
    assert cfg.min_participants == 3
    assert cfg.aggregation_method == "fedavg"
    assert cfg.differential_privacy is True
    assert cfg.fedprox_mu == pytest.approx(0.01)


def test_model_update_dataclass_fields():
    now = datetime.now()
    upd = ModelUpdate(
        participant_id="p1",
        model_weights={"a": np.zeros(2)},
        num_samples=10,
        loss=0.1,
        accuracy=0.9,
        timestamp=now,
        signature="sig",
    )
    assert upd.participant_id == "p1"
    assert upd.timestamp is now
    assert upd.signature == "sig"


def test_service_initial_state(service):
    assert service.global_model is None
    assert service.participants == {}
    assert service.round_history == []
    assert isinstance(service.encryption_key, bytes)
    assert isinstance(service.config, FederatedConfig)


def test_module_level_singleton_exists():
    assert isinstance(fls.federated_learning_service, FederatedLearningService)


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------
def test_generate_encryption_key_is_stable_and_urlsafe_b64(service):
    key = service._generate_encryption_key()
    assert key == service.encryption_key
    assert len(base64.urlsafe_b64decode(key)) == 32


def test_encrypt_decrypt_roundtrip(service):
    payload = {"w": np.arange(6, dtype=float).reshape(2, 3), "n": 7}
    blob = service._encrypt_data(payload)
    assert isinstance(blob, bytes)
    assert blob != payload
    restored = service._decrypt_data(blob)
    assert restored["n"] == 7
    np.testing.assert_allclose(restored["w"], payload["w"])


def test_sign_and_verify_update(service):
    upd = ModelUpdate("p1", {}, 10, 0.25, 0.75, datetime.now(), "")
    sig = service._sign_update(upd)
    assert len(sig) == 64
    upd.signature = sig
    assert service._verify_signature(upd) is True
    upd.signature = "not-the-signature"
    assert service._verify_signature(upd) is False


def test_sign_update_depends_on_payload(service):
    a = ModelUpdate("p1", {}, 10, 0.25, 0.75, datetime.now(), "")
    b = ModelUpdate("p2", {}, 10, 0.25, 0.75, datetime.now(), "")
    assert service._sign_update(a) != service._sign_update(b)


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------
def test_create_global_model_neural_network(service):
    model = service._create_global_model("neural_network")
    assert isinstance(model, nn.Module)
    assert hasattr(model, "fc1") and hasattr(model, "fc2") and hasattr(model, "fc3")


def test_create_global_model_random_forest(service):
    from sklearn.ensemble import RandomForestClassifier

    model = service._create_global_model("random_forest")
    assert isinstance(model, RandomForestClassifier)
    assert model.n_estimators == 100


def test_create_global_model_logistic_regression(service):
    from sklearn.linear_model import LogisticRegression

    model = service._create_global_model("logistic_regression")
    assert isinstance(model, LogisticRegression)
    assert model.max_iter == 1000


def test_create_global_model_unsupported_raises(service):
    with pytest.raises(ValueError, match="Unsupported model type"):
        service._create_global_model("svm")


def test_neural_network_forward_pass_shape(service):
    net = service._create_neural_network()
    x = torch.tensor(np.zeros((3, 1000)), dtype=torch.float32)
    out = net(x)
    assert tuple(out.shape) == (3, 2)


def test_neural_network_named_parameters_present(service):
    net = service._create_neural_network()
    names = {name for name, _ in net.named_parameters()}
    assert "fc1.weight" in names
    assert "fc3.bias" in names


# ---------------------------------------------------------------------------
# initialize_federated_training
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_initialize_federated_training_happy_path(service, session_factory):
    cfg = FederatedConfig(min_participants=2, aggregation_method="fedavg")
    result = await service.initialize_federated_training(
        "logistic_regression", cfg, ["p1", "p2"]
    )
    assert result["status"] == "initialized"
    assert result["idempotent"] is False
    assert result["participants"] == ["p1", "p2"]
    assert result["round_id"].startswith("round_")
    assert result["config"]["min_participants"] == 2
    assert set(service.participants) == {"p1", "p2"}

    db = session_factory()
    try:
        assert db.query(FederatedParticipant).count() == 2
        assert db.query(FederatedRound).count() == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_initialize_federated_training_idempotency(service, session_factory):
    cfg = FederatedConfig(min_participants=1)
    first = await service.initialize_federated_training(
        "logistic_regression", cfg, ["p1"], idempotency_key="key-1"
    )
    assert first["idempotent"] is False

    db = session_factory()
    try:
        assert db.query(FederatedIdempotency).count() == 1
    finally:
        db.close()

    second = await service.initialize_federated_training(
        "logistic_regression", cfg, ["p9"], idempotency_key="key-1"
    )
    assert second["idempotent"] is True
    assert second["round_id"] == first["round_id"]
    # Participants echo back the *requested* list, not the stored one.
    assert second["participants"] == ["p9"]


@pytest.mark.asyncio
async def test_initialize_federated_training_propagates_errors(
    service, session_factory
):
    with pytest.raises(ValueError, match="Unsupported model type"):
        await service.initialize_federated_training(
            "not_a_model", FederatedConfig(), ["p1"]
        )


@pytest.mark.asyncio
async def test_register_participant_error_is_reraised(service, monkeypatch):
    @contextmanager
    def _boom():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(fls, "db_session", _boom)
    with pytest.raises(RuntimeError, match="db down"):
        await service._register_participant("p1")


@pytest.mark.asyncio
async def test_create_federated_round_error_is_reraised(service, monkeypatch):
    @contextmanager
    def _boom():
        raise RuntimeError("no round")
        yield  # pragma: no cover

    monkeypatch.setattr(fls, "db_session", _boom)
    with pytest.raises(RuntimeError, match="no round"):
        await service._create_federated_round()


# ---------------------------------------------------------------------------
# submit_model_update
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_submit_model_update_persists_encrypted_weights(service, session_factory):
    weights = _weights(1.0)
    result = await service.submit_model_update(
        participant_id="p1",
        model_weights=weights,
        num_samples=40,
        loss=0.3,
        accuracy=0.85,
        round_id="round_x",
        meta_data={"site": "a"},
    )
    assert result["status"] == "submitted"
    assert result["participant_id"] == "p1"
    assert result["round_id"] == "round_x"
    datetime.fromisoformat(result["timestamp"])  # parses

    db = session_factory()
    try:
        row = db.query(FederatedModel).one()
        assert row.num_samples == 40
        assert row.is_aggregated is False
        assert row.meta_data == {"site": "a"}
        decrypted = service._decrypt_data(row.model_weights)
        np.testing.assert_allclose(decrypted["bias1"], weights["bias1"])
    finally:
        db.close()


@pytest.mark.asyncio
async def test_submit_model_update_bad_signature_raises(
    service, session_factory, monkeypatch
):
    monkeypatch.setattr(service, "_verify_signature", lambda update: False)
    with pytest.raises(ValueError, match="Invalid model update signature"):
        await service.submit_model_update("p1", _weights(1.0), 10, 0.1, 0.9)


@pytest.mark.asyncio
async def test_submit_model_update_db_error_is_reraised(service, monkeypatch):
    @contextmanager
    def _boom():
        raise RuntimeError("write failed")
        yield  # pragma: no cover

    monkeypatch.setattr(fls, "db_session", _boom)
    with pytest.raises(RuntimeError, match="write failed"):
        await service.submit_model_update("p1", _weights(1.0), 10, 0.1, 0.9)


# ---------------------------------------------------------------------------
# aggregate_models
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_models_insufficient_participants(service, session_factory):
    service.config = FederatedConfig(min_participants=3)
    _insert_update(service, session_factory, "r1", "p1", _weights(1.0), 10)
    with pytest.raises(ValueError, match="Insufficient participants"):
        await service.aggregate_models("r1")


@pytest.mark.asyncio
async def test_aggregate_models_fedavg_weighted_average(service, session_factory):
    service.config = FederatedConfig(min_participants=2, aggregation_method="fedavg")
    _insert_update(service, session_factory, "r1", "p1", _weights(0.0), 10)
    _insert_update(service, session_factory, "r1", "p2", _weights(1.0), 30)
    # Different round: must be ignored.
    _insert_update(service, session_factory, "r2", "p3", _weights(100.0), 50)

    result = await service.aggregate_models("r1")

    assert result["status"] == "aggregated"
    assert result["round_id"] == "r1"
    assert result["num_participants"] == 2
    assert result["global_model_id"] == "global_r1"
    # 10/40 * 0 + 30/40 * 1 == 0.75
    np.testing.assert_allclose(result["aggregated_weights"]["bias1"], 0.75)
    np.testing.assert_allclose(result["aggregated_weights"]["layer1"], 0.75)

    metrics = result["metrics"]
    assert metrics["total_samples"] == 40
    assert metrics["min_samples"] == 10
    assert metrics["max_samples"] == 30
    assert metrics["mean_accuracy"] == pytest.approx(0.8)
    assert metrics["std_loss"] == pytest.approx(0.0)

    db = session_factory()
    try:
        aggregated_flags = {
            row.round_id: row.is_aggregated for row in db.query(FederatedModel).all()
        }
        assert aggregated_flags["r1"] is True
        assert aggregated_flags["r2"] is False

        global_row = db.query(FederatedGlobalModel).one()
        assert global_row.model_id == "global_r1"
        assert global_row.version == 1
        # No global model was created, so the persisted type is the fallback.
        assert global_row.model_type == "unknown"
        persisted = pickle.loads(global_row.model_weights)
        np.testing.assert_allclose(persisted["bias1"], 0.75)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_aggregate_models_global_model_persist_failure_is_swallowed(
    service, session_factory, monkeypatch
):
    service.config = FederatedConfig(min_participants=2)
    _insert_update(service, session_factory, "r1", "p1", _weights(1.0), 10)
    _insert_update(service, session_factory, "r1", "p2", _weights(1.0), 10)

    def _boom(**kwargs):
        raise RuntimeError("cannot build global model row")

    monkeypatch.setattr(fls, "FederatedGlobalModel", _boom)

    result = await service.aggregate_models("r1")
    assert result["status"] == "aggregated"

    db = session_factory()
    try:
        assert db.query(FederatedGlobalModel).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_aggregate_models_increments_prometheus_counter(
    service, session_factory, monkeypatch
):
    calls = []

    class _Counter:
        def labels(self, **kwargs):
            calls.append(kwargs)
            return self

        def inc(self):
            calls.append("inc")

    fake_metrics = types.ModuleType("app.observability.metrics")
    fake_metrics.FEDERATED_ROUNDS = _Counter()
    monkeypatch.setitem(sys.modules, "app.observability.metrics", fake_metrics)

    service.config = FederatedConfig(min_participants=2)
    _insert_update(service, session_factory, "r1", "p1", _weights(1.0), 10)
    _insert_update(service, session_factory, "r1", "p2", _weights(1.0), 10)

    await service.aggregate_models("r1")
    assert calls == [{"phase": "aggregate"}, "inc"]


@pytest.mark.asyncio
async def test_aggregate_models_db_error_is_reraised(service, monkeypatch):
    @contextmanager
    def _boom():
        raise RuntimeError("aggregate boom")
        yield  # pragma: no cover

    monkeypatch.setattr(fls, "db_session", _boom)
    with pytest.raises(RuntimeError, match="aggregate boom"):
        await service.aggregate_models("r1")


# ---------------------------------------------------------------------------
# Aggregation strategies
# ---------------------------------------------------------------------------
class _FakeUpdate:
    """Light stand-in for a ``FederatedModel`` row."""

    def __init__(self, blob, num_samples, meta_data=None, loss=0.5, accuracy=0.8):
        self.model_weights = blob
        self.num_samples = num_samples
        self.meta_data = meta_data
        self.loss = loss
        self.accuracy = accuracy


@pytest.mark.asyncio
async def test_federated_averaging_empty_returns_empty_dict(service):
    assert await service._federated_averaging([]) == {}


@pytest.mark.asyncio
async def test_aggregate_weights_dispatch_fedprox(service):
    service.config = FederatedConfig(aggregation_method="fedprox")
    updates = [
        _FakeUpdate(service._encrypt_data(_weights(0.0)), 1),
        _FakeUpdate(service._encrypt_data(_weights(2.0)), 3),
    ]
    out = await service._aggregate_weights(updates)
    np.testing.assert_allclose(out["bias1"], 1.5)


@pytest.mark.asyncio
async def test_aggregate_weights_dispatch_fednova(service):
    service.config = FederatedConfig(aggregation_method="fednova")
    updates = [_FakeUpdate(service._encrypt_data(_weights(4.0)), 5)]
    out = await service._aggregate_weights(updates)
    np.testing.assert_allclose(out["bias1"], 4.0)


@pytest.mark.asyncio
async def test_aggregate_weights_unsupported_method_raises(service):
    service.config = FederatedConfig(aggregation_method="mystery")
    with pytest.raises(ValueError, match="Unsupported aggregation method"):
        await service._aggregate_weights([_FakeUpdate(b"", 1)])


@pytest.mark.asyncio
async def test_secure_aggregation_protocol_delegates_to_fedavg(service):
    service.config = FederatedConfig(aggregation_method="fedavg")
    updates = [
        _FakeUpdate(service._encrypt_data(_weights(1.0)), 2),
        _FakeUpdate(service._encrypt_data(_weights(3.0)), 2),
    ]
    out = await service.secure_aggregation_protocol(updates)
    np.testing.assert_allclose(out["bias1"], 2.0)


@pytest.mark.asyncio
async def test_secure_aggregation_protocol_reraises(service):
    async def _boom(_updates):
        raise RuntimeError("secure boom")

    service._federated_averaging = _boom
    with pytest.raises(RuntimeError, match="secure boom"):
        await service.secure_aggregation_protocol([])


@pytest.mark.parametrize(
    "setting_name,meta_key",
    [
        ("FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED", "use_bonawitz_mask"),
        ("FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED", "use_ring_masked"),
    ],
)
@pytest.mark.asyncio
async def test_federated_averaging_ring_masked_paths(
    service, monkeypatch, setting_name, meta_key
):
    from app.services.federated_ring_mask import ring_masks, verify_zero_sum

    monkeypatch.setattr(fls.settings, setting_name, True, raising=False)
    service.config = FederatedConfig(aggregation_method="fedavg")

    nums = [10, 30]
    values = [np.full(3, 0.0), np.full(3, 1.0)]
    masks = ring_masks(2, 3, seed=17)
    assert verify_zero_sum(masks)

    updates = []
    for n, v, m in zip(nums, values, masks):
        payload = {"bias1": n * v + m}
        updates.append(
            _FakeUpdate(service._encrypt_data(payload), n, meta_data={meta_key: True})
        )

    out = await service._federated_averaging(updates)
    np.testing.assert_allclose(out["bias1"], np.full(3, 0.75), atol=1e-9)


@pytest.mark.asyncio
async def test_ring_mask_not_used_when_meta_flag_missing(service, monkeypatch):
    monkeypatch.setattr(
        fls.settings, "FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED", True, raising=False
    )
    service.config = FederatedConfig(aggregation_method="fedavg")
    updates = [
        _FakeUpdate(service._encrypt_data(_weights(2.0)), 10, meta_data=None),
        _FakeUpdate(service._encrypt_data(_weights(2.0)), 10, meta_data={}),
    ]
    out = await service._federated_averaging(updates)
    np.testing.assert_allclose(out["bias1"], 2.0)


# ---------------------------------------------------------------------------
# Global model update / retrieval
# ---------------------------------------------------------------------------
def test_update_global_model_sklearn_branch_is_noop(service):
    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression()
    service.global_model = model
    assert service._update_global_model({"anything": np.zeros(2)}) is None
    assert service.global_model is model


class _TinyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(2, 2)


def test_update_global_model_neural_network_branch(service):
    net = _TinyNet()
    service.global_model = net
    aggregated = {
        "fc.weight": np.zeros((2, 2), dtype=float),
        "fc.bias": np.zeros(2, dtype=float),
    }
    assert service._update_global_model(aggregated) is None
    assert service.global_model is net


@pytest.mark.asyncio
async def test_get_global_model_uninitialized_raises(service):
    with pytest.raises(ValueError, match="Global model not initialized"):
        await service.get_global_model("p1")


@pytest.mark.asyncio
async def test_get_global_model_sklearn_returns_params(service):
    from sklearn.linear_model import LogisticRegression

    service.global_model = LogisticRegression(max_iter=1000)
    result = await service.get_global_model("p1")
    assert result["model_type"] == "LogisticRegression"
    datetime.fromisoformat(result["timestamp"])
    params = service._decrypt_data(result["model_weights"])
    assert params["max_iter"] == 1000


@pytest.mark.asyncio
async def test_get_global_model_neural_network_returns_named_weights(service):
    service.global_model = service._create_neural_network()
    result = await service.get_global_model("p1")
    assert result["model_type"] == "BiomarkerNet"
    weights = service._decrypt_data(result["model_weights"])
    assert "fc1.weight" in weights
    assert weights["fc1.weight"].shape == (512, 1000)


@pytest.mark.asyncio
async def test_get_global_model_reraises_on_encrypt_failure(service, monkeypatch):
    from sklearn.linear_model import LogisticRegression

    service.global_model = LogisticRegression()

    def _boom(_data):
        raise RuntimeError("encrypt boom")

    monkeypatch.setattr(service, "_encrypt_data", _boom)
    with pytest.raises(RuntimeError, match="encrypt boom"):
        await service.get_global_model("p1")


# ---------------------------------------------------------------------------
# evaluate_global_model
# ---------------------------------------------------------------------------
class _ConstantNet(nn.Module):
    """Always predicts class 1 regardless of the input."""

    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(4, 2)

    def forward(self, x):
        n_rows = x.shape[0]
        return torch.tensor(np.tile(np.array([0.1, 0.9]), (n_rows, 1)))


@pytest.mark.asyncio
async def test_evaluate_global_model_uninitialized_raises(service):
    with pytest.raises(ValueError, match="Global model not initialized"):
        await service.evaluate_global_model(pd.DataFrame({"a": [1.0]}), pd.Series([0]))


@pytest.mark.asyncio
async def test_evaluate_global_model_sklearn(service):
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(7)
    X = pd.DataFrame(rng.standard_normal((30, 5)), columns=list("abcde"))
    y = pd.Series((X["a"] > 0).astype(int).values)
    model = LogisticRegression(random_state=42, max_iter=1000).fit(X, y)
    service.global_model = model

    result = await service.evaluate_global_model(X, y)
    for key in ("accuracy", "precision", "recall", "f1_score"):
        assert 0.0 <= result[key] <= 1.0
    assert result["num_samples"] == 30
    datetime.fromisoformat(result["timestamp"])


@pytest.mark.asyncio
async def test_evaluate_global_model_neural_network(service):
    service.global_model = _ConstantNet()
    X = pd.DataFrame(np.zeros((6, 4)), columns=list("abcd"))
    y = pd.Series([1] * 6)

    result = await service.evaluate_global_model(X, y)
    assert result["accuracy"] == pytest.approx(1.0)
    assert result["num_samples"] == 6


@pytest.mark.asyncio
async def test_evaluate_global_model_single_row(service):
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(3)
    X = pd.DataFrame(rng.standard_normal((20, 3)), columns=list("abc"))
    y = pd.Series(([0] * 10) + ([1] * 10))
    service.global_model = LogisticRegression(max_iter=200).fit(X, y)

    result = await service.evaluate_global_model(X.iloc[[0]], y.iloc[[0]])
    assert result["num_samples"] == 1
    assert result["accuracy"] in (0.0, 1.0)


@pytest.mark.asyncio
async def test_evaluate_global_model_reraises_on_predict_failure(service):
    class _Broken:
        def predict(self, _X):
            raise RuntimeError("predict boom")

    service.global_model = _Broken()
    with pytest.raises(RuntimeError, match="predict boom"):
        await service.evaluate_global_model(pd.DataFrame({"a": [1.0]}), pd.Series([0]))


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_federated_status_empty_db(service, session_factory):
    status = await service.get_federated_status()
    assert status["active_participants"] == 0
    assert status["recent_updates"] == 0
    assert status["global_model_initialized"] is False
    assert status["recent_rounds"] == []
    assert status["config"]["aggregation_method"] == "fedavg"


@pytest.mark.asyncio
async def test_get_federated_status_with_data(service, session_factory):
    cfg = FederatedConfig(min_participants=1)
    await service.initialize_federated_training("random_forest", cfg, ["p1", "p2"])
    await service.submit_model_update("p1", _weights(1.0), 5, 0.2, 0.9, round_id="r1")

    status = await service.get_federated_status()
    assert status["active_participants"] == 2
    assert status["recent_updates"] == 1
    assert status["global_model_initialized"] is True
    assert len(status["recent_rounds"]) == 1
    entry = status["recent_rounds"][0]
    assert entry["status"] == "active"
    datetime.fromisoformat(entry["started_at"])


@pytest.mark.asyncio
async def test_get_federated_status_db_error_is_reraised(service, monkeypatch):
    @contextmanager
    def _boom():
        raise RuntimeError("status boom")
        yield  # pragma: no cover

    monkeypatch.setattr(fls, "db_session", _boom)
    with pytest.raises(RuntimeError, match="status boom"):
        await service.get_federated_status()


# ---------------------------------------------------------------------------
# Differential privacy
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_add_differential_privacy_noise_shapes_and_change(service):
    np.random.seed(1234)
    weights = {"w": np.zeros((4, 3)), "b": np.zeros(3)}
    noisy = await service.add_differential_privacy_noise(weights, epsilon=1.0)
    assert set(noisy) == {"w", "b"}
    assert noisy["w"].shape == (4, 3)
    assert noisy["b"].shape == (3,)
    assert not np.allclose(noisy["w"], 0.0)


@pytest.mark.asyncio
async def test_add_differential_privacy_noise_smaller_epsilon_is_noisier(service):
    np.random.seed(0)
    weights = {"w": np.zeros(500)}
    low_privacy = await service.add_differential_privacy_noise(weights, epsilon=10.0)
    np.random.seed(0)
    high_privacy = await service.add_differential_privacy_noise(weights, epsilon=0.5)
    assert np.std(high_privacy["w"]) > np.std(low_privacy["w"])


@pytest.mark.asyncio
async def test_add_differential_privacy_noise_empty_weights(service):
    assert await service.add_differential_privacy_noise({}) == {}


@pytest.mark.asyncio
async def test_add_differential_privacy_noise_reraises_on_bad_input(service):
    with pytest.raises(AttributeError):
        await service.add_differential_privacy_noise({"w": [1.0, 2.0, 3.0]})
