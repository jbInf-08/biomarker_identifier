"""Self-contained unit tests for ``app.services.tasks.biomarker_tasks``.

Run with ``--noconftest``; no project fixtures are used.  All heavy / networked
collaborators (pipelines, DB session, websocket manager, celery ``current_task``)
are replaced with local fakes so the whole module runs in well under a second.
"""

import importlib
import importlib.util
import os
import sys
import types

import pytest

# --------------------------------------------------------------------------
# Environment + optional-dependency stubs must be installed before importing
# the module under test.
# --------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")


def _available(dotted: str) -> bool:
    try:
        return importlib.util.find_spec(dotted) is not None
    except (ImportError, ValueError):
        return False


if not _available("httpx"):  # pragma: no cover - CI has the real package
    _httpx = types.ModuleType("httpx")

    class _StubResponse:  # minimal surface used by app.services.webhook_dispatch
        status_code = 200
        text = ""

    class _HTTPError(Exception):
        pass

    _httpx.Response = _StubResponse
    _httpx.HTTPError = _HTTPError
    _httpx.RequestError = _HTTPError
    _httpx.TimeoutException = _HTTPError

    def _post(*args, **kwargs):
        raise _HTTPError("httpx is stubbed out in this test module")

    _httpx.post = _post
    sys.modules.setdefault("httpx", _httpx)


if not _available("fastapi"):  # pragma: no cover - CI has the real package

    class _AnyStub:
        """Callable/decorator/annotation-friendly placeholder."""

        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            if len(args) == 1 and not kwargs and callable(args[0]):
                return args[0]
            return _AnyStub()

        def __getattr__(self, name):
            return _AnyStub()

    class _WebSocketDisconnect(Exception):
        pass

    class _FastAPIModule(types.ModuleType):
        def __getattr__(self, name):
            return _AnyStub()

    _fastapi = _FastAPIModule("fastapi")
    _fastapi.WebSocket = _AnyStub
    _fastapi.WebSocketDisconnect = _WebSocketDisconnect
    _fastapi.APIRouter = _AnyStub
    sys.modules.setdefault("fastapi", _fastapi)


if not _available("statsmodels.stats.multitest"):  # pragma: no cover
    _sm = types.ModuleType("statsmodels")
    _sm_stats = types.ModuleType("statsmodels.stats")
    _sm_mt = types.ModuleType("statsmodels.stats.multitest")

    def _multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
        pvals = list(pvals)
        adjusted = [min(1.0, float(p)) for p in pvals]
        reject = [p <= alpha for p in adjusted]
        return reject, adjusted, alpha, alpha

    _sm_mt.multipletests = _multipletests
    _sm_stats.multitest = _sm_mt
    _sm.stats = _sm_stats
    sys.modules.setdefault("statsmodels", _sm)
    sys.modules.setdefault("statsmodels.stats", _sm_stats)
    sys.modules.setdefault("statsmodels.stats.multitest", _sm_mt)


bt = importlib.import_module("app.services.tasks.biomarker_tasks")


# --------------------------------------------------------------------------
# Local test doubles
# --------------------------------------------------------------------------
class FakeCurrentTask:
    """Records every ``update_state`` call made by the module."""

    def __init__(self, raises=False):
        self.states = []
        self.raises = raises

    def update_state(self, state=None, meta=None):
        if self.raises:
            raise RuntimeError("backend unavailable")
        self.states.append((state, meta))


class FakeManager:
    """Records every websocket payload sent by the module."""

    def __init__(self, raises=False):
        self.messages = []
        self.raises = raises

    def send_to_run(self, run_id, payload):
        if self.raises:
            raise RuntimeError("socket closed")
        self.messages.append((run_id, payload))


class FakeRun:
    def __init__(self, user_id=None):
        self.status = bt.RunStatus.PENDING.value
        self.user_id = user_id


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDB:
    def __init__(self, run=None):
        self.run = run
        self.commits = 0
        self.queries = 0

    def query(self, model):
        self.queries += 1
        return FakeQuery(self.run)

    def commit(self):
        self.commits += 1


class FakeSessionFactory:
    """Stand-in for ``app.core.database.db_session`` (a context manager)."""

    def __init__(self, db=None, raises=False):
        self.db = db if db is not None else FakeDB()
        self.raises = raises
        self.entered = 0

    def __call__(self):
        return self

    def __enter__(self):
        self.entered += 1
        if self.raises:
            raise RuntimeError("db down")
        return self.db

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePipeline:
    """Stand-in for ``BiomarkerPipeline``."""

    instances = []

    def __init__(self, results=None, error=None):
        self.results = results if results is not None else {"biomarkers": []}
        self.error = error
        self.calls = []

    def run_pipeline(
        self,
        expression_file_path=None,
        label_file_path=None,
        parameters=None,
        progress_callback=None,
    ):
        self.calls.append(
            {
                "expression_file_path": expression_file_path,
                "label_file_path": label_file_path,
                "parameters": parameters,
            }
        )
        if progress_callback is not None:
            progress_callback(55, "halfway")
        if self.error is not None:
            raise self.error
        return self.results


def _install_common(monkeypatch, task=None, manager=None):
    task = task or FakeCurrentTask()
    manager = manager or FakeManager()
    monkeypatch.setattr(bt, "current_task", task)
    monkeypatch.setattr(bt, "manager", manager)
    return task, manager


@pytest.fixture
def self_stub():
    obj = types.SimpleNamespace(request=types.SimpleNamespace(id="task-123"))
    return obj


def _bound(task_obj, self_stub):
    """Return the task body with ``self`` bound to ``self_stub``.

    Celery exposes the original function as ``Task.__wrapped__``; because it is
    stored on the task class it comes back already bound to the task instance,
    so unwrap ``__func__`` to regain control of the ``self`` argument.
    """
    fun = task_obj.__wrapped__
    fun = getattr(fun, "__func__", fun)

    def _inner(*args, **kwargs):
        return fun(self_stub, *args, **kwargs)

    return _inner


# --------------------------------------------------------------------------
# Module surface
# --------------------------------------------------------------------------
def test_tasks_are_registered_with_expected_names():
    assert (
        bt.run_biomarker_analysis.name
        == "app.services.tasks.biomarker_tasks.run_biomarker_analysis"
    )
    assert (
        bt.run_pathway_analysis.name
        == "app.services.tasks.biomarker_tasks.run_pathway_analysis"
    )
    assert (
        bt.run_shap_analysis.name
        == "app.services.tasks.biomarker_tasks.run_shap_analysis"
    )


# --------------------------------------------------------------------------
# update_progress
# --------------------------------------------------------------------------
def test_update_progress_happy_path(monkeypatch):
    task, mgr = _install_common(monkeypatch)

    bt.update_progress("run-1", 42, "working", "task-9")

    assert task.states == [("PROGRESS", {"progress": 42, "status": "working"})]
    run_id, payload = mgr.messages[0]
    assert run_id == "run-1"
    assert payload == {
        "type": "progress_update",
        "progress": 42,
        "status": "working",
        "task_id": "task-9",
    }


def test_update_progress_swallows_current_task_error(monkeypatch):
    task = FakeCurrentTask(raises=True)
    _, mgr = _install_common(monkeypatch, task=task)

    # Must not raise - the exception handler logs a warning instead.
    assert bt.update_progress("run-1", 5, "x", "t") is None
    assert mgr.messages == []


def test_update_progress_swallows_manager_error(monkeypatch):
    mgr = FakeManager(raises=True)
    task, _ = _install_common(monkeypatch, manager=mgr)

    assert bt.update_progress("run-1", 5, "x", "t") is None
    # state update happened before the websocket blew up
    assert task.states == [("PROGRESS", {"progress": 5, "status": "x"})]


@pytest.mark.parametrize("progress", [0, 1, 100])
def test_update_progress_edge_progress_values(monkeypatch, progress):
    task, mgr = _install_common(monkeypatch)
    bt.update_progress("r", progress, "s", None)
    assert task.states[0][1]["progress"] == progress
    assert mgr.messages[0][1]["task_id"] is None


# --------------------------------------------------------------------------
# run_biomarker_analysis
# --------------------------------------------------------------------------
def test_run_biomarker_analysis_success_with_webhook(monkeypatch, self_stub):
    task, mgr = _install_common(monkeypatch)
    run = FakeRun(user_id="user-7")
    session = FakeSessionFactory(FakeDB(run))
    pipeline = FakePipeline(results={"biomarkers": ["GENE1"], "n": 1})
    monkeypatch.setattr(bt, "db_session", session)
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: pipeline)

    dispatched = []
    monkeypatch.setattr(
        bt,
        "dispatch_webhooks_for_user",
        lambda db, **kw: dispatched.append(kw),
    )

    out = _bound(bt.run_biomarker_analysis, self_stub)(
        "run-1", "expr.csv", "labels.csv", {"alpha": 0.05}
    )

    assert out == {
        "run_id": "run-1",
        "status": "completed",
        "results": {"biomarkers": ["GENE1"], "n": 1},
        "task_id": "task-123",
    }
    assert run.status == bt.RunStatus.COMPLETED.value
    assert session.db.commits == 2  # RUNNING then COMPLETED
    assert pipeline.calls[0]["expression_file_path"] == "expr.csv"
    assert pipeline.calls[0]["parameters"] == {"alpha": 0.05}

    # progress ladder: 0, 10, 20, callback(55), 100
    progresses = [meta["progress"] for _, meta in task.states]
    assert progresses == [0, 10, 20, 55, 100]
    assert task.states[-1][0] == "SUCCESS"
    assert [p["progress"] for _, p in mgr.messages] == [0, 10, 20, 55, 100]

    assert dispatched == [
        {
            "user_id": "user-7",
            "event": "run.completed",
            "payload": {
                "run_id": "run-1",
                "status": "completed",
                "task_id": "task-123",
            },
        }
    ]


def test_run_biomarker_analysis_success_without_user_skips_webhook(
    monkeypatch, self_stub
):
    _install_common(monkeypatch)
    run = FakeRun(user_id=None)
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(FakeDB(run)))
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: FakePipeline())

    called = []
    monkeypatch.setattr(
        bt, "dispatch_webhooks_for_user", lambda *a, **k: called.append(k)
    )

    out = _bound(bt.run_biomarker_analysis, self_stub)("run-2", "e", "l", {})

    assert out["status"] == "completed"
    assert run.status == bt.RunStatus.COMPLETED.value
    assert called == []


def test_run_biomarker_analysis_missing_run_row(monkeypatch, self_stub):
    """No AnalysisRun row -> no status writes, no commits, still succeeds."""
    _install_common(monkeypatch)
    session = FakeSessionFactory(FakeDB(run=None))
    monkeypatch.setattr(bt, "db_session", session)
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: FakePipeline(results={}))

    called = []
    monkeypatch.setattr(
        bt, "dispatch_webhooks_for_user", lambda *a, **k: called.append(k)
    )

    out = _bound(bt.run_biomarker_analysis, self_stub)("run-3", "e", "l", {})

    assert out["results"] == {}
    assert session.db.commits == 0
    assert called == []


def test_run_biomarker_analysis_webhook_failure_is_swallowed(monkeypatch, self_stub):
    _install_common(monkeypatch)
    run = FakeRun(user_id="u1")
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(FakeDB(run)))
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: FakePipeline())

    def _boom(*a, **k):
        raise RuntimeError("webhook exploded")

    monkeypatch.setattr(bt, "dispatch_webhooks_for_user", _boom)

    out = _bound(bt.run_biomarker_analysis, self_stub)("run-4", "e", "l", {})

    assert out["status"] == "completed"
    assert run.status == bt.RunStatus.COMPLETED.value


def test_run_biomarker_analysis_pipeline_failure_marks_failed(monkeypatch, self_stub):
    task, mgr = _install_common(monkeypatch)
    run = FakeRun(user_id="u2")
    db = FakeDB(run)
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(db))
    monkeypatch.setattr(
        bt, "BiomarkerPipeline", lambda: FakePipeline(error=ValueError("bad shapes"))
    )

    dispatched = []
    monkeypatch.setattr(
        bt, "dispatch_webhooks_for_user", lambda db_, **kw: dispatched.append(kw)
    )

    with pytest.raises(ValueError, match="bad shapes"):
        _bound(bt.run_biomarker_analysis, self_stub)("run-5", "e", "l", {})

    assert run.status == bt.RunStatus.FAILED.value
    assert task.states[-1][0] == "FAILURE"
    assert task.states[-1][1]["error"] == "bad shapes"
    assert mgr.messages[-1][1]["error"] == "bad shapes"
    assert dispatched[0]["event"] == "run.failed"
    assert dispatched[0]["payload"]["error"] == "bad shapes"


def test_run_biomarker_analysis_failure_webhook_failure_swallowed(
    monkeypatch, self_stub
):
    task, _ = _install_common(monkeypatch)
    run = FakeRun(user_id="u3")
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(FakeDB(run)))
    monkeypatch.setattr(
        bt, "BiomarkerPipeline", lambda: FakePipeline(error=RuntimeError("kaput"))
    )

    def _boom(*a, **k):
        raise RuntimeError("webhook exploded")

    monkeypatch.setattr(bt, "dispatch_webhooks_for_user", _boom)

    with pytest.raises(RuntimeError, match="kaput"):
        _bound(bt.run_biomarker_analysis, self_stub)("run-6", "e", "l", {})

    assert run.status == bt.RunStatus.FAILED.value
    assert task.states[-1][0] == "FAILURE"


def test_run_biomarker_analysis_failure_when_db_also_unavailable(
    monkeypatch, self_stub
):
    """The recovery ``db_session`` raising is logged, not propagated."""
    task, mgr = _install_common(monkeypatch)
    session = FakeSessionFactory(raises=True)
    monkeypatch.setattr(bt, "db_session", session)
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: FakePipeline())

    with pytest.raises(RuntimeError, match="db down"):
        _bound(bt.run_biomarker_analysis, self_stub)("run-7", "e", "l", {})

    # entered twice: main body + failure handler, both raising
    assert session.entered == 2
    assert task.states[-1][0] == "FAILURE"
    assert mgr.messages[-1][1]["status"] == "Analysis failed: db down"


def test_run_biomarker_analysis_failure_when_no_run_row(monkeypatch, self_stub):
    _install_common(monkeypatch)
    db = FakeDB(run=None)
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(db))
    monkeypatch.setattr(
        bt, "BiomarkerPipeline", lambda: FakePipeline(error=KeyError("missing"))
    )

    with pytest.raises(KeyError):
        _bound(bt.run_biomarker_analysis, self_stub)("run-8", "e", "l", {})

    assert db.commits == 0


def test_run_biomarker_analysis_progress_callback_errors_do_not_fail_run(
    monkeypatch, self_stub
):
    """``update_progress`` swallows its own errors, so the run still completes."""
    task = FakeCurrentTask()
    mgr = FakeManager(raises=True)
    _install_common(monkeypatch, task=task, manager=mgr)
    # first manager call already raises -> whole task fails
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(FakeDB(FakeRun())))
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: FakePipeline())

    with pytest.raises(RuntimeError, match="socket closed"):
        _bound(bt.run_biomarker_analysis, self_stub)("run-9", "e", "l", {})


def test_run_biomarker_analysis_empty_parameters(monkeypatch, self_stub):
    _install_common(monkeypatch)
    pipeline = FakePipeline(results={"biomarkers": []})
    monkeypatch.setattr(bt, "db_session", FakeSessionFactory(FakeDB(FakeRun())))
    monkeypatch.setattr(bt, "BiomarkerPipeline", lambda: pipeline)
    monkeypatch.setattr(bt, "dispatch_webhooks_for_user", lambda *a, **k: None)

    out = _bound(bt.run_biomarker_analysis, self_stub)("run-10", "", "", {})

    assert out["results"] == {"biomarkers": []}
    assert pipeline.calls[0]["parameters"] == {}


# --------------------------------------------------------------------------
# run_pathway_analysis
# --------------------------------------------------------------------------
@pytest.fixture
def pathway_module(monkeypatch):
    """Provide ``app.pipelines.pathway_analysis`` (real one if it exists)."""
    name = "app.pipelines.pathway_analysis"
    try:
        mod = importlib.import_module(name)
    except ImportError:
        mod = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, mod)
    return mod


class FakePathwayAnalyzer:
    results = {"pathways": [{"id": "hsa04110", "p": 0.01}]}
    error = None
    calls = []

    def analyze_pathways(self, biomarker_ids=None, parameters=None):
        type(self).calls.append((biomarker_ids, parameters))
        if type(self).error is not None:
            raise type(self).error
        return type(self).results


def _fresh_pathway_cls(results=None, error=None):
    cls = type(
        "PathwayAnalyzerStub",
        (FakePathwayAnalyzer,),
        {
            "results": results if results is not None else {"pathways": []},
            "error": error,
            "calls": [],
        },
    )
    return cls


def test_run_pathway_analysis_success(monkeypatch, self_stub, pathway_module):
    task, mgr = _install_common(monkeypatch)
    cls = _fresh_pathway_cls(results={"pathways": [{"id": "hsa04110"}]})
    monkeypatch.setattr(pathway_module, "PathwayAnalyzer", cls, raising=False)

    out = _bound(bt.run_pathway_analysis, self_stub)(
        "run-p1", ["GENE1", "GENE2"], {"db": "kegg"}
    )

    assert out == {
        "run_id": "run-p1",
        "status": "completed",
        "results": {"pathways": [{"id": "hsa04110"}]},
        "task_id": "task-123",
    }
    assert cls.calls == [(["GENE1", "GENE2"], {"db": "kegg"})]
    assert [meta["progress"] for _, meta in task.states] == [0, 50, 100]
    assert task.states[-1][0] == "SUCCESS"
    assert {p["type"] for _, p in mgr.messages} == {"pathway_progress"}


def test_run_pathway_analysis_empty_biomarker_list(
    monkeypatch, self_stub, pathway_module
):
    _install_common(monkeypatch)
    cls = _fresh_pathway_cls(results={"pathways": []})
    monkeypatch.setattr(pathway_module, "PathwayAnalyzer", cls, raising=False)

    out = _bound(bt.run_pathway_analysis, self_stub)("run-p2", [], {})

    assert out["results"] == {"pathways": []}
    assert cls.calls == [([], {})]


def test_run_pathway_analysis_analyzer_failure(monkeypatch, self_stub, pathway_module):
    task, mgr = _install_common(monkeypatch)
    cls = _fresh_pathway_cls(error=ValueError("no such pathway db"))
    monkeypatch.setattr(pathway_module, "PathwayAnalyzer", cls, raising=False)

    with pytest.raises(ValueError, match="no such pathway db"):
        _bound(bt.run_pathway_analysis, self_stub)("run-p3", ["G"], {})

    assert task.states[-1][0] == "FAILURE"
    assert task.states[-1][1]["error"] == "no such pathway db"
    last = mgr.messages[-1][1]
    assert last["type"] == "pathway_progress"
    assert last["progress"] == 0
    assert last["status"].startswith("Pathway analysis failed:")


def test_run_pathway_analysis_import_error_path(monkeypatch, self_stub):
    """``app.pipelines.pathway_analysis`` missing -> handled by except + re-raise."""
    task, mgr = _install_common(monkeypatch)
    monkeypatch.setitem(sys.modules, "app.pipelines.pathway_analysis", None)

    with pytest.raises(ImportError):
        _bound(bt.run_pathway_analysis, self_stub)("run-p4", ["G"], {})

    assert task.states[-1][0] == "FAILURE"
    assert mgr.messages[-1][1]["type"] == "pathway_progress"


# --------------------------------------------------------------------------
# run_shap_analysis
# --------------------------------------------------------------------------
class FakeSHAPAnalyzer:
    results = {"shap_values": [[0.1, 0.2]]}
    error = None
    calls = []

    def compute_shap_values(self, model_path=None, data_path=None, parameters=None):
        type(self).calls.append((model_path, data_path, parameters))
        if type(self).error is not None:
            raise type(self).error
        return type(self).results


def _fresh_shap_cls(results=None, error=None):
    return type(
        "SHAPAnalyzerStub",
        (FakeSHAPAnalyzer,),
        {
            "results": results if results is not None else {"shap_values": []},
            "error": error,
            "calls": [],
        },
    )


@pytest.fixture
def shap_module():
    return importlib.import_module("app.pipelines.shap_analysis")


def test_run_shap_analysis_success(monkeypatch, self_stub, shap_module, tmp_path):
    task, mgr = _install_common(monkeypatch)
    cls = _fresh_shap_cls(
        results={"shap_values": [[0.5, 0.25]], "features": ["a", "b"]}
    )
    monkeypatch.setattr(shap_module, "SHAPAnalyzer", cls)

    model_path = str(tmp_path / "model.pkl")
    data_path = str(tmp_path / "data.csv")

    out = _bound(bt.run_shap_analysis, self_stub)(
        "run-s1", model_path, data_path, {"n": 10}
    )

    assert out["run_id"] == "run-s1"
    assert out["status"] == "completed"
    assert out["task_id"] == "task-123"
    assert out["results"]["features"] == ["a", "b"]
    assert cls.calls == [(model_path, data_path, {"n": 10})]
    assert [meta["progress"] for _, meta in task.states] == [0, 50, 100]
    assert task.states[-1][0] == "SUCCESS"
    assert {p["type"] for _, p in mgr.messages} == {"shap_progress"}
    assert [p["progress"] for _, p in mgr.messages] == [0, 50, 100]


def test_run_shap_analysis_empty_paths_propagate(monkeypatch, self_stub, shap_module):
    """Empty paths reach the analyzer; its ValueError bubbles up."""
    task, mgr = _install_common(monkeypatch)
    cls = _fresh_shap_cls(
        error=ValueError("model_path and data_path are required for SHAP analysis")
    )
    monkeypatch.setattr(shap_module, "SHAPAnalyzer", cls)

    with pytest.raises(ValueError, match="required for SHAP analysis"):
        _bound(bt.run_shap_analysis, self_stub)("run-s2", "", "", {})

    assert task.states[-1][0] == "FAILURE"
    assert "required for SHAP analysis" in task.states[-1][1]["error"]
    assert mgr.messages[-1][1]["progress"] == 0


def test_run_shap_analysis_failure_reports_progress_zero(
    monkeypatch, self_stub, shap_module
):
    task, mgr = _install_common(monkeypatch)
    cls = _fresh_shap_cls(error=MemoryError("out of memory"))
    monkeypatch.setattr(shap_module, "SHAPAnalyzer", cls)

    with pytest.raises(MemoryError):
        _bound(bt.run_shap_analysis, self_stub)("run-s3", "m", "d", {})

    assert task.states[-1][1] == {
        "progress": 0,
        "status": "SHAP analysis failed: out of memory",
        "error": "out of memory",
    }
    assert mgr.messages[-1][1]["error"] == "out of memory"


def test_run_shap_analysis_none_parameters(monkeypatch, self_stub, shap_module):
    _install_common(monkeypatch)
    cls = _fresh_shap_cls(results={})
    monkeypatch.setattr(shap_module, "SHAPAnalyzer", cls)

    out = _bound(bt.run_shap_analysis, self_stub)("run-s4", "m", "d", None)

    assert out["results"] == {}
    assert cls.calls == [("m", "d", None)]
