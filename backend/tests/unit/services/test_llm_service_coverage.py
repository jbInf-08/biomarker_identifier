"""
Self-contained unit tests for app/services/llm_service.py.

Runnable with --noconftest: no project fixtures are used, every external or
optional dependency (transformers, datasets, peft, openai, prometheus_client)
is stubbed only when the real package is unavailable, and all network / model
access is mocked.
"""

import json
import os
import sys
import types
from importlib.util import find_spec

import pytest

# app.core.config validates these at import time.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")


def _install_prometheus_stub():
    """app.observability.metrics needs prometheus_client; stub only if missing."""
    if find_spec("prometheus_client") is not None:
        return
    mod = types.ModuleType("prometheus_client")

    class _Metric:
        def __init__(self, *args, **kwargs):
            self._name = args[0] if args else ""

        def labels(self, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            return None

        def observe(self, *args, **kwargs):
            return None

    class _Registry:
        _collector_to_names = {}

    mod.REGISTRY = _Registry()
    mod.Counter = _Metric
    mod.Histogram = _Metric
    mod.generate_latest = lambda *args, **kwargs: b""
    sys.modules["prometheus_client"] = mod


_install_prometheus_stub()

from app.services import llm_service as mod  # noqa: E402
from app.services.llm_service import LLMConfig, LLMService, train_llm  # noqa: E402

# ---------------------------------------------------------------------------
# helpers / fakes
# ---------------------------------------------------------------------------


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


def _fake_openai_new(content=" hello from openai ", raises=False):
    """openai module exposing the modern OpenAI client class."""
    m = types.ModuleType("openai")

    class _Completions:
        def create(self, **kwargs):
            if raises:
                raise RuntimeError("boom")
            _Completions.last_kwargs = kwargs
            return _Resp(content)

    class _Chat:
        completions = _Completions()

    class OpenAI:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.chat = _Chat()

    m.OpenAI = OpenAI
    m._completions_cls = _Completions
    return m


def _fake_openai_legacy(content=" legacy text "):
    """openai module WITHOUT the OpenAI class -> legacy ChatCompletion path."""
    m = types.ModuleType("openai")

    class ChatCompletion:
        last_kwargs = None

        @staticmethod
        def create(**kwargs):
            ChatCompletion.last_kwargs = kwargs
            return _Resp(content)

    m.ChatCompletion = ChatCompletion
    return m


def _fake_transformers(pipeline_impl=None, tokenizer_impl=None):
    m = types.ModuleType("transformers")

    def _default_pipeline(*args, **kwargs):
        return lambda *a, **k: [{"generated_text": "out"}]

    class _AutoTok:
        @staticmethod
        def from_pretrained(model_id):
            if tokenizer_impl is not None:
                return tokenizer_impl(model_id)
            return object()

    m.pipeline = pipeline_impl or _default_pipeline
    m.AutoTokenizer = _AutoTok
    m.AutoModelForCausalLM = object
    return m


class _Settings:
    """Minimal stand-in for app.core.config.settings."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture(autouse=True)
def _reset_module_globals():
    """llm_service caches pipelines in module globals; isolate every test."""
    saved = (
        mod._pipeline,
        mod._tokenizer,
        mod._TRANSFORMERS_AVAILABLE,
        mod._OPENAI_AVAILABLE,
        mod.settings,
    )
    mod._pipeline = None
    mod._tokenizer = None
    mod._TRANSFORMERS_AVAILABLE = False
    mod._OPENAI_AVAILABLE = False
    yield
    (
        mod._pipeline,
        mod._tokenizer,
        mod._TRANSFORMERS_AVAILABLE,
        mod._OPENAI_AVAILABLE,
        mod.settings,
    ) = saved


@pytest.fixture
def openai_ready(monkeypatch):
    """settings with an API key + an importable fake openai module."""
    fake = _fake_openai_new()
    monkeypatch.setattr(mod, "settings", _Settings(OPENAI_API_KEY="sk-test"))
    monkeypatch.setitem(sys.modules, "openai", fake)
    return fake


# ---------------------------------------------------------------------------
# _load_transformers
# ---------------------------------------------------------------------------


def test_load_transformers_returns_true_when_pipeline_already_cached(monkeypatch):
    sentinel = object()
    mod._pipeline = sentinel
    assert mod._load_transformers() is True
    assert mod._pipeline is sentinel


def test_load_transformers_import_error_returns_false(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", None)
    assert mod._load_transformers() is False
    assert mod._pipeline is None


def test_load_transformers_happy_path_uses_default_model(monkeypatch):
    seen = {}

    def _pipeline(task, **kwargs):
        seen["task"] = task
        seen["kwargs"] = kwargs
        return lambda *a, **k: [{"generated_text": "x"}]

    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_pipeline))

    assert mod._load_transformers() is True
    assert mod._TRANSFORMERS_AVAILABLE is True
    assert mod._pipeline is not None
    assert mod._tokenizer is not None
    assert seen["task"] == "text2text-generation"
    assert seen["kwargs"]["model"] == "google/flan-t5-base"
    assert seen["kwargs"]["device"] == -1
    assert seen["kwargs"]["max_length"] == 256


def test_load_transformers_uses_model_id_from_settings(monkeypatch):
    seen = {}

    def _pipeline(task, **kwargs):
        seen["model"] = kwargs.get("model")
        return lambda *a, **k: [{"generated_text": "x"}]

    monkeypatch.setattr(mod, "settings", _Settings(LLM_MODEL_ID="my/custom-model"))
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_pipeline))

    assert mod._load_transformers() is True
    assert seen["model"] == "my/custom-model"


def test_load_transformers_falls_back_to_summarization(monkeypatch):
    calls = []

    def _pipeline(task, **kwargs):
        calls.append(task)
        if task == "text2text-generation":
            raise RuntimeError("primary model unavailable")
        return lambda *a, **k: [{"summary_text": "s"}]

    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_pipeline))

    assert mod._load_transformers() is True
    assert calls == ["text2text-generation", "summarization"]
    assert mod._pipeline is not None
    # the tokenizer line is never reached on the fallback branch
    assert mod._tokenizer is None


def test_load_transformers_both_pipelines_fail(monkeypatch):
    def _pipeline(task, **kwargs):
        raise RuntimeError(f"no {task}")

    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers(_pipeline))

    assert mod._load_transformers() is False
    assert mod._pipeline is None


def test_load_transformers_tokenizer_failure_triggers_fallback(monkeypatch):
    """AutoTokenizer.from_pretrained blowing up is caught by the same handler."""

    def _tok(model_id):
        raise RuntimeError("tokenizer download failed")

    calls = []

    def _pipeline(task, **kwargs):
        calls.append(task)
        return lambda *a, **k: [{"generated_text": "x"}]

    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(
        sys.modules, "transformers", _fake_transformers(_pipeline, _tok)
    )

    assert mod._load_transformers() is True
    assert calls == ["text2text-generation", "summarization"]


# ---------------------------------------------------------------------------
# _openai_available
# ---------------------------------------------------------------------------


def test_openai_available_false_without_settings(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    assert mod._openai_available() is False


def test_openai_available_false_without_api_key(monkeypatch):
    monkeypatch.setattr(mod, "settings", _Settings(OPENAI_API_KEY=None))
    assert mod._openai_available() is False


def test_openai_available_true_with_key_and_module(monkeypatch, openai_ready):
    assert mod._openai_available() is True
    assert mod._OPENAI_AVAILABLE is True


def test_openai_available_false_when_import_fails(monkeypatch):
    monkeypatch.setattr(mod, "settings", _Settings(OPENAI_API_KEY="sk-test"))
    monkeypatch.setitem(sys.modules, "openai", None)
    assert mod._openai_available() is False


# ---------------------------------------------------------------------------
# LLMConfig / construction
# ---------------------------------------------------------------------------


def test_llm_config_defaults():
    cfg = LLMConfig()
    assert cfg.use_openai_if_available is True
    assert cfg.default_max_tokens == 256
    assert cfg.temperature == pytest.approx(0.3)


def test_service_uses_default_config_when_none():
    svc = LLMService()
    assert isinstance(svc.config, LLMConfig)
    assert svc._pipe is None
    assert svc._openai_client is None


def test_service_accepts_custom_config():
    cfg = LLMConfig(use_openai_if_available=False, default_max_tokens=32, temperature=0)
    svc = LLMService(cfg)
    assert svc.config is cfg


# ---------------------------------------------------------------------------
# _get_pipeline
# ---------------------------------------------------------------------------


def test_get_pipeline_returns_cached_instance():
    svc = LLMService()
    svc._pipe = "cached"
    assert svc._get_pipeline() == "cached"


def test_get_pipeline_loads_module_global(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers())
    svc = LLMService()
    pipe = svc._get_pipeline()
    assert pipe is not None
    assert pipe is mod._pipeline
    # second call short-circuits on the instance cache
    assert svc._get_pipeline() is pipe


def test_get_pipeline_none_when_transformers_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", None)
    assert LLMService()._get_pipeline() is None


# ---------------------------------------------------------------------------
# _call_openai
# ---------------------------------------------------------------------------


def test_call_openai_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    assert LLMService()._call_openai("hi") is None


def test_call_openai_modern_client(monkeypatch, openai_ready):
    svc = LLMService()
    out = svc._call_openai("prompt-text", system="be careful", max_tokens=77)
    assert out == "hello from openai"
    kwargs = openai_ready._completions_cls.last_kwargs
    assert kwargs["model"] == "gpt-3.5-turbo"
    assert kwargs["max_tokens"] == 77
    assert kwargs["temperature"] == pytest.approx(0.3)
    assert kwargs["messages"] == [
        {"role": "system", "content": "be careful"},
        {"role": "user", "content": "prompt-text"},
    ]


def test_call_openai_without_system_defaults_max_tokens(monkeypatch, openai_ready):
    svc = LLMService(LLMConfig(default_max_tokens=11))
    out = svc._call_openai("only-user")
    assert out == "hello from openai"
    kwargs = openai_ready._completions_cls.last_kwargs
    assert kwargs["max_tokens"] == 11
    assert kwargs["messages"] == [{"role": "user", "content": "only-user"}]


def test_call_openai_legacy_chatcompletion(monkeypatch):
    fake = _fake_openai_legacy()
    monkeypatch.setattr(mod, "settings", _Settings(OPENAI_API_KEY="sk-legacy"))
    monkeypatch.setitem(sys.modules, "openai", fake)

    out = LLMService()._call_openai("p", system="s")
    assert out == "legacy text"
    assert fake.ChatCompletion.last_kwargs["api_key"] == "sk-legacy"
    assert fake.ChatCompletion.last_kwargs["model"] == "gpt-3.5-turbo"


def test_call_openai_swallows_exceptions(monkeypatch):
    monkeypatch.setattr(mod, "settings", _Settings(OPENAI_API_KEY="sk-test"))
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_new(raises=True))
    assert LLMService()._call_openai("p") is None


# ---------------------------------------------------------------------------
# _call_hf
# ---------------------------------------------------------------------------


def test_call_hf_returns_none_without_pipeline(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", None)
    assert LLMService()._call_hf("p") is None


def test_call_hf_success_and_kwargs():
    captured = {}

    def _pipe(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return [{"generated_text": "  generated  "}]

    svc = LLMService(LLMConfig(temperature=0.9, default_max_tokens=64))
    svc._pipe = _pipe
    assert svc._call_hf("hello") == "generated"
    assert captured["prompt"] == "hello"
    assert captured["max_length"] == 64
    assert captured["do_sample"] is True
    assert captured["temperature"] == pytest.approx(0.9)


def test_call_hf_explicit_max_length_wins():
    captured = {}

    def _pipe(prompt, **kwargs):
        captured.update(kwargs)
        return [{"generated_text": "ok"}]

    svc = LLMService()
    svc._pipe = _pipe
    assert svc._call_hf("hello", max_length=5) == "ok"
    assert captured["max_length"] == 5


def test_call_hf_empty_output_returns_none():
    svc = LLMService()
    svc._pipe = lambda prompt, **kwargs: []
    assert svc._call_hf("hello") is None


def test_call_hf_missing_generated_text_key_returns_empty_string():
    svc = LLMService()
    svc._pipe = lambda prompt, **kwargs: [{"summary_text": "s"}]
    assert svc._call_hf("hello") == ""


def test_call_hf_swallows_exceptions():
    def _boom(prompt, **kwargs):
        raise RuntimeError("pipeline exploded")

    svc = LLMService()
    svc._pipe = _boom
    assert svc._call_hf("hello") is None


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def test_generate_prefers_openai(monkeypatch, openai_ready):
    svc = LLMService()
    svc._pipe = lambda *a, **k: [{"generated_text": "hf"}]
    assert svc.generate("p") == "hello from openai"


def test_generate_falls_back_to_hf_when_openai_returns_none(monkeypatch):
    monkeypatch.setattr(mod, "settings", _Settings(OPENAI_API_KEY="sk-test"))
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_new(raises=True))
    svc = LLMService()
    svc._pipe = lambda *a, **k: [{"generated_text": "hf answer"}]
    assert svc.generate("p") == "hf answer"


def test_generate_skips_openai_when_disabled_by_config(monkeypatch, openai_ready):
    svc = LLMService(LLMConfig(use_openai_if_available=False))
    svc._pipe = lambda *a, **k: [{"generated_text": "hf only"}]
    assert svc.generate("p") == "hf only"


def test_generate_returns_fallback_message_when_no_backend(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    out = LLMService().generate("p")
    assert out.startswith("(LLM unavailable")
    assert "OPENAI_API_KEY" in out


def test_generate_fallback_message_on_empty_hf_string(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    svc = LLMService()
    svc._pipe = lambda *a, **k: [{"generated_text": "   "}]
    assert svc.generate("p").startswith("(LLM unavailable")


# ---------------------------------------------------------------------------
# convenience wrappers
# ---------------------------------------------------------------------------


def test_summarize_literature_truncates_and_forwards(monkeypatch):
    calls = {}

    def _gen(prompt, system=None, max_tokens=None):
        calls["prompt"] = prompt
        calls["max_tokens"] = max_tokens
        return "summary"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)
    assert svc.summarize_literature("A" * 5000, max_length=42) == "summary"
    assert calls["max_tokens"] == 42
    assert calls["prompt"].startswith("Summarize the following biomedical text")
    assert calls["prompt"].count("A") == 3000


def test_summarize_literature_empty_text(monkeypatch):
    svc = LLMService()
    monkeypatch.setattr(svc, "generate", lambda p, **k: "empty-ok")
    assert svc.summarize_literature("") == "empty-ok"


def test_explain_biomarker_without_context(monkeypatch):
    calls = {}

    def _gen(prompt, system=None, max_tokens=None):
        calls["prompt"] = prompt
        calls["max_tokens"] = max_tokens
        return "explanation"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)
    assert svc.explain_biomarker(["TP53", "BRCA1"]) == "explanation"
    assert "TP53, BRCA1" in calls["prompt"]
    assert "Context:" not in calls["prompt"]
    assert calls["max_tokens"] == 200


def test_explain_biomarker_caps_genes_and_truncates_context(monkeypatch):
    calls = {}

    def _gen(prompt, system=None, max_tokens=None):
        calls["prompt"] = prompt
        return "x"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)
    genes = [f"G{i}" for i in range(30)]
    svc.explain_biomarker(genes, context="Z" * 900)
    assert "G19" in calls["prompt"]
    assert "G20" not in calls["prompt"]
    assert "Context: " in calls["prompt"]
    assert calls["prompt"].count("Z") == 500


def test_explain_biomarker_empty_gene_list(monkeypatch):
    calls = {}
    svc = LLMService()
    monkeypatch.setattr(
        svc, "generate", lambda p, **k: calls.setdefault("prompt", p) and "y" or "y"
    )
    assert svc.explain_biomarker([]) == "y"
    assert "these genes: ." in calls["prompt"]


def test_annotate_clinical_text(monkeypatch):
    calls = {}

    def _gen(prompt, system=None, max_tokens=None):
        calls["prompt"] = prompt
        calls["max_tokens"] = max_tokens
        return "annotated"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)
    assert svc.annotate_clinical_text("B" * 4000) == "annotated"
    assert calls["max_tokens"] == 200
    assert calls["prompt"].count("B") == 2000


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_true_via_openai(monkeypatch, openai_ready):
    assert LLMService().is_available() is True


def test_is_available_true_via_pipeline(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", _fake_transformers())
    assert LLMService().is_available() is True


def test_is_available_false_when_no_backend(monkeypatch):
    monkeypatch.setattr(mod, "settings", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    assert LLMService().is_available() is False


# ---------------------------------------------------------------------------
# grounded_interpret_pipeline
# ---------------------------------------------------------------------------


@pytest.fixture
def grounding(monkeypatch):
    """Patch retrieve_all_sources so no snippet file / PubMed call is needed."""
    import app.services.llm_grounding as grounding_mod

    state = {
        "merged": [
            {
                "id": "s1",
                "title": "TP53 and cell cycle",
                "text": "TP53 regulates apoptosis.",
                "source_type": "corpus",
            }
        ],
        "matched": ["TP53"],
        "api_sources": [{"id": "s1", "title": "TP53 and cell cycle", "pmid": None}],
    }

    def _fake(genes, local_limit=6):
        state["genes"] = list(genes)
        return state["merged"], state["matched"], state["api_sources"]

    monkeypatch.setattr(grounding_mod, "retrieve_all_sources", _fake)
    return state


def test_grounded_interpret_structured_json_parsed(monkeypatch, grounding):
    payload = {
        "summary": "s",
        "limitations": "l",
        "suggested_validation": "v",
    }
    text = "Paragraph one.\n\nParagraph two.\n" + json.dumps(payload)

    captured = {}

    def _gen(prompt, system=None, max_tokens=None):
        captured["prompt"] = prompt
        captured["system"] = system
        captured["max_tokens"] = max_tokens
        return text

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)

    out = svc.grounded_interpret_pipeline(
        ["TP53", "BRCA1"],
        pipeline_summary={"auc": 0.8},
        extra_context="notes here",
        max_tokens=128,
    )

    assert set(out) == {"interpretation", "sources", "matched_genes", "structured"}
    assert out["interpretation"] == text
    assert out["sources"] == grounding["api_sources"]
    assert out["matched_genes"] == ["TP53"]
    assert out["structured"] == payload
    assert captured["max_tokens"] == 128
    assert captured["system"].startswith("You are a careful biomedical assistant")
    assert "[corpus::TP53 and cell cycle]" in captured["prompt"]
    assert "TP53 regulates apoptosis." in captured["prompt"]
    assert "Additional notes: notes here" in captured["prompt"]
    assert '"summary": "..."' in captured["prompt"]
    assert '"auc": 0.8' in captured["prompt"]


def test_grounded_interpret_structured_false_skips_json(monkeypatch, grounding):
    captured = {}

    def _gen(prompt, system=None, max_tokens=None):
        captured["prompt"] = prompt
        return 'text with {"summary": "ignored"}'

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)

    out = svc.grounded_interpret_pipeline(["TP53"], structured=False)
    assert out["structured"] == {}
    assert "output exactly one JSON object" not in captured["prompt"]
    assert "Additional notes" not in captured["prompt"]


def test_grounded_interpret_invalid_json_yields_empty_structured(
    monkeypatch, grounding
):
    svc = LLMService()
    monkeypatch.setattr(
        svc, "generate", lambda *a, **k: "prose then {not valid json at all"
    )
    out = svc.grounded_interpret_pipeline(["TP53"])
    assert out["structured"] == {}


def test_grounded_interpret_no_brace_in_text(monkeypatch, grounding):
    svc = LLMService()
    monkeypatch.setattr(svc, "generate", lambda *a, **k: "plain prose, no json here")
    out = svc.grounded_interpret_pipeline(["TP53"])
    assert out["structured"] == {}
    assert out["interpretation"] == "plain prose, no json here"


def test_grounded_interpret_json_missing_keys_defaults_to_empty(monkeypatch, grounding):
    svc = LLMService()
    monkeypatch.setattr(svc, "generate", lambda *a, **k: '{"summary": "only summary"}')
    out = svc.grounded_interpret_pipeline(["TP53"])
    assert out["structured"] == {
        "summary": "only summary",
        "limitations": "",
        "suggested_validation": "",
    }


def test_grounded_interpret_non_dict_json_leaves_structured_empty(
    monkeypatch, grounding
):
    svc = LLMService()
    monkeypatch.setattr(svc, "generate", lambda *a, **k: "text {1, 2, 3}")
    out = svc.grounded_interpret_pipeline(["TP53"])
    assert out["structured"] == {}


def test_grounded_interpret_no_sources_and_no_genes(monkeypatch, grounding):
    grounding["merged"] = []
    grounding["matched"] = []
    grounding["api_sources"] = []
    captured = {}

    def _gen(prompt, system=None, max_tokens=None):
        captured["prompt"] = prompt
        return "nothing to say"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)

    out = svc.grounded_interpret_pipeline([])
    assert "(No matching grounding passages for these genes.)" in captured["prompt"]
    assert out["sources"] == []
    assert out["matched_genes"] == []


def test_grounded_interpret_snippet_without_title_falls_back_to_id(
    monkeypatch, grounding
):
    grounding["merged"] = [
        {"id": "abc123", "source_type": "pubmed"},
        {"text": "orphan body"},
    ]
    captured = {}

    def _gen(prompt, system=None, max_tokens=None):
        captured["prompt"] = prompt
        return "ok"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)
    svc.grounded_interpret_pipeline(["TP53"])
    assert "[pubmed::abc123]" in captured["prompt"]
    assert "[corpus::snippet]" in captured["prompt"]
    assert "orphan body" in captured["prompt"]


def test_grounded_interpret_caps_genes_and_matched_genes(monkeypatch, grounding):
    grounding["matched"] = [f"M{i}" for i in range(30)]
    captured = {}

    def _gen(prompt, system=None, max_tokens=None):
        captured["prompt"] = prompt
        return "ok"

    svc = LLMService()
    monkeypatch.setattr(svc, "generate", _gen)
    out = svc.grounded_interpret_pipeline([f"G{i}" for i in range(50)])

    assert len(out["matched_genes"]) == 20
    assert "G39" in captured["prompt"]
    assert "G40" not in captured["prompt"]


# ---------------------------------------------------------------------------
# train_llm
# ---------------------------------------------------------------------------


class _FakeTokenizerOut(dict):
    pass


class _FakeTokenizer:
    pad_token_id = 0

    def __init__(self):
        self.saved_to = None

    def __call__(self, texts, max_length=None, truncation=None, padding=None):
        return _FakeTokenizerOut({"input_ids": [[1, 2, 0] for _ in texts]})

    def save_pretrained(self, path):
        self.saved_to = path


class _FakeDataset:
    def __init__(self, data):
        self.data = data
        self.mapped = None

    @classmethod
    def from_dict(cls, d):
        return cls(d)

    def map(self, fn, batched=False, remove_columns=None):
        self.mapped = fn(self.data)
        return self


def _fake_train_modules(peft_available=True):
    """Return (patch-dict, state) stubbing transformers/datasets/peft for train_llm."""
    state = {"trained": False, "saved_to": None, "peft_applied": False, "args": None}

    datasets_mod = types.ModuleType("datasets")
    datasets_mod.Dataset = _FakeDataset

    tf_mod = types.ModuleType("transformers")
    tokenizer = _FakeTokenizer()

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(model_id):
            return tokenizer

    class AutoModelForSeq2SeqLM:
        @staticmethod
        def from_pretrained(model_id):
            return {"model": model_id}

    class TrainingArguments:
        def __init__(self, **kwargs):
            state["args"] = kwargs

    class Trainer:
        def __init__(self, model=None, args=None, train_dataset=None):
            self.model = model
            self.dataset = train_dataset

        def train(self):
            state["trained"] = True

        def save_model(self, out):
            state["saved_to"] = out

    tf_mod.AutoTokenizer = AutoTokenizer
    tf_mod.AutoModelForSeq2SeqLM = AutoModelForSeq2SeqLM
    tf_mod.AutoModelForCausalLM = object
    tf_mod.pipeline = lambda *a, **k: None
    tf_mod.Trainer = Trainer
    tf_mod.TrainingArguments = TrainingArguments

    mods = {"datasets": datasets_mod, "transformers": tf_mod}

    if peft_available:
        peft_mod = types.ModuleType("peft")

        class LoraConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class TaskType:
            SEQ_2_SEQ_LM = "SEQ_2_SEQ_LM"

        def get_peft_model(model, config):
            state["peft_applied"] = True
            return model

        peft_mod.LoraConfig = LoraConfig
        peft_mod.TaskType = TaskType
        peft_mod.get_peft_model = get_peft_model
        mods["peft"] = peft_mod
    else:
        mods["peft"] = None

    state["tokenizer"] = tokenizer
    return mods, state


def _apply_modules(monkeypatch, mods):
    for name, m in mods.items():
        monkeypatch.setitem(sys.modules, name, m)


def test_train_llm_missing_dependencies_returns_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "datasets", None)
    result = train_llm([{"input": "a", "target": "b"}])
    assert result["success"] is False
    assert "error" in result


def test_train_llm_rejects_empty_data(monkeypatch):
    mods, _ = _fake_train_modules()
    _apply_modules(monkeypatch, mods)
    result = train_llm([])
    assert result["success"] is False
    assert "train_data must be a path" in result["error"]


def test_train_llm_rejects_non_dict_records(monkeypatch):
    mods, _ = _fake_train_modules()
    _apply_modules(monkeypatch, mods)
    result = train_llm(["not-a-dict"])
    assert result["success"] is False


def test_train_llm_happy_path_with_peft(monkeypatch, tmp_path):
    mods, state = _fake_train_modules(peft_available=True)
    _apply_modules(monkeypatch, mods)
    out_dir = str(tmp_path / "model_out")

    result = train_llm(
        [
            {"input": "gene A", "target": "summary A"},
            {"input": "gene B", "target": "summary B"},
        ],
        base_model_id="tiny/model",
        output_dir=out_dir,
        num_epochs=1,
        batch_size=2,
        use_peft=True,
    )

    assert result == {
        "success": True,
        "output_dir": out_dir,
        "num_samples": 2,
        "base_model": "tiny/model",
        "use_peft": True,
    }
    assert state["trained"] is True
    assert state["saved_to"] == out_dir
    assert state["peft_applied"] is True
    assert state["tokenizer"].saved_to == out_dir
    assert state["args"]["num_train_epochs"] == 1
    assert state["args"]["per_device_train_batch_size"] == 2
    assert state["args"]["report_to"] == "none"
    assert os.path.isdir(out_dir)


def test_train_llm_without_peft(monkeypatch, tmp_path):
    mods, state = _fake_train_modules(peft_available=True)
    _apply_modules(monkeypatch, mods)
    result = train_llm(
        [{"input": "x", "target": "y"}],
        output_dir=str(tmp_path / "out2"),
        use_peft=False,
    )
    assert result["use_peft"] is False
    assert state["peft_applied"] is False


def test_train_llm_disables_peft_when_package_missing(monkeypatch, tmp_path):
    mods, state = _fake_train_modules(peft_available=False)
    _apply_modules(monkeypatch, mods)
    result = train_llm(
        [{"input": "x", "target": "y"}],
        output_dir=str(tmp_path / "out3"),
        use_peft=True,
    )
    assert result["success"] is True
    assert result["use_peft"] is False
    assert state["peft_applied"] is False


def test_train_llm_reads_json_file(monkeypatch, tmp_path):
    mods, state = _fake_train_modules()
    _apply_modules(monkeypatch, mods)
    data_file = tmp_path / "train.json"
    data_file.write_text(
        json.dumps([{"input": "i1", "target": "t1"}, {"input": "i2", "target": "t2"}]),
        encoding="utf-8",
    )
    result = train_llm(
        str(data_file), output_dir=str(tmp_path / "out4"), use_peft=False
    )
    assert result["success"] is True
    assert result["num_samples"] == 2


def test_train_llm_reads_jsonl_file_with_alt_keys(monkeypatch, tmp_path):
    mods, state = _fake_train_modules()
    _apply_modules(monkeypatch, mods)
    data_file = tmp_path / "train.jsonl"
    data_file.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"text": "alt in 1", "summary": "alt out 1"},
                {"text": "alt in 2", "summary": "alt out 2"},
            ]
        ),
        encoding="utf-8",
    )
    result = train_llm(
        str(data_file), output_dir=str(tmp_path / "out5"), use_peft=False
    )
    assert result["success"] is True
    assert result["num_samples"] == 2
    # tokenize_fn masks pad tokens with -100
    mapped = state["tokenizer"]
    assert mapped.saved_to == str(tmp_path / "out5")


def test_train_llm_tokenize_fn_masks_padding(monkeypatch, tmp_path):
    """The mapped dataset holds labels with pad ids replaced by -100."""
    mods, state = _fake_train_modules()
    _apply_modules(monkeypatch, mods)

    captured = {}
    original_map = _FakeDataset.map

    def _map(self, fn, batched=False, remove_columns=None):
        result = original_map(self, fn, batched=batched, remove_columns=remove_columns)
        captured["mapped"] = self.mapped
        return result

    monkeypatch.setattr(_FakeDataset, "map", _map)

    train_llm(
        [{"input": "a", "target": "b"}],
        output_dir=str(tmp_path / "out6"),
        use_peft=False,
    )
    assert captured["mapped"]["labels"] == [[1, 2, -100]]
    assert captured["mapped"]["input_ids"] == [[1, 2, 0]]
