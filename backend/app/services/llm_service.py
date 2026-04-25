"""
LLM Service for Biomarker Discovery.

Provides inference and optional fine-tuning of large language models for:
- Literature summarization and annotation
- Biomarker explanation and report generation
- Clinical text interpretation

Supports Hugging Face Transformers (local/offline) and optional OpenAI API.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from app.core.config import settings
except ImportError:
    settings = None

_TRANSFORMERS_AVAILABLE = False
_OPENAI_AVAILABLE = False
_pipeline = None
_tokenizer = None


def _load_transformers():
    """Lazy load Hugging Face pipeline."""
    global _TRANSFORMERS_AVAILABLE, _pipeline, _tokenizer
    if _pipeline is not None:
        return True
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

        _TRANSFORMERS_AVAILABLE = True
        # Use a small model by default (runs on CPU); override with env if needed
        model_id = getattr(settings, "LLM_MODEL_ID", None) if settings else None
        if not model_id:
            model_id = (
                "google/flan-t5-base"  # summarization + generation, reasonable size
            )
        try:
            _pipeline = pipeline(
                "text2text-generation",
                model=model_id,
                tokenizer=model_id,
                max_length=256,
                device=-1,  # CPU
            )
            _tokenizer = AutoTokenizer.from_pretrained(model_id)
        except Exception as e:
            logger.warning(
                f"Could not load {model_id}, trying summarization pipeline: {e}"
            )
            try:
                _pipeline = pipeline(
                    "summarization", model="facebook/bart-large-cnn", device=-1
                )
            except Exception as e2:
                logger.warning(f"Summarization fallback failed: {e2}")
                _pipeline = None
        return _pipeline is not None
    except ImportError:
        logger.warning(
            "transformers not installed. LLM features disabled. pip install transformers"
        )
        return False


def _openai_available() -> bool:
    global _OPENAI_AVAILABLE
    if not settings or not getattr(settings, "OPENAI_API_KEY", None):
        return False
    try:
        import openai

        _OPENAI_AVAILABLE = True
        return True
    except ImportError:
        return False


@dataclass
class LLMConfig:
    """LLM service configuration."""

    use_openai_if_available: bool = True
    default_max_tokens: int = 256
    temperature: float = 0.3


class LLMService:
    """
    Service for LLM inference and optional fine-tuning.
    Uses Hugging Face by default; OpenAI when API key is set.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._pipe = None
        self._openai_client = None

    def _get_pipeline(self):
        if self._pipe is not None:
            return self._pipe
        if _load_transformers():
            self._pipe = _pipeline
        return self._pipe

    def _call_openai(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        if not _openai_available() or not settings:
            return None
        try:
            import openai

            api_key = getattr(settings, "OPENAI_API_KEY", None)
            max_tokens = max_tokens or self.config.default_max_tokens
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            if hasattr(openai, "OpenAI"):
                client = openai.OpenAI(api_key=api_key)
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=self.config.temperature,
                )
            else:
                resp = openai.ChatCompletion.create(
                    api_key=api_key,
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=self.config.temperature,
                )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"OpenAI call failed: {e}")
            return None

    def _call_hf(self, prompt: str, max_length: Optional[int] = None) -> Optional[str]:
        pipe = self._get_pipeline()
        if pipe is None:
            return None
        try:
            max_length = max_length or self.config.default_max_tokens
            out = pipe(
                prompt,
                max_length=max_length,
                do_sample=True,
                temperature=self.config.temperature,
            )
            if out and len(out) > 0:
                return out[0].get("generated_text", "").strip()
            return None
        except Exception as e:
            logger.warning(f"Hugging Face pipeline failed: {e}")
            return None

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from prompt. Tries OpenAI first if configured, else Hugging Face."""
        if self.config.use_openai_if_available and _openai_available():
            result = self._call_openai(prompt, system=system, max_tokens=max_tokens)
            if result:
                return result
        result = self._call_hf(
            prompt, max_length=max_tokens or self.config.default_max_tokens
        )
        return (
            result
            or "(LLM unavailable or returned empty. Install transformers and/or set OPENAI_API_KEY.)"
        )

    def summarize_literature(self, text: str, max_length: int = 150) -> str:
        """Summarize a literature abstract or paragraph."""
        prompt = f"Summarize the following biomedical text in one or two sentences: {text[:3000]}"
        return self.generate(prompt, max_tokens=max_length)

    def explain_biomarker(
        self, gene_symbols: List[str], context: Optional[str] = None
    ) -> str:
        """Generate a short explanation of biomarker relevance from gene symbols."""
        genes = ", ".join(gene_symbols[:20])
        prompt = f"Briefly explain the potential clinical or biomarker relevance of these genes: {genes}."
        if context:
            prompt += f" Context: {context[:500]}"
        return self.generate(prompt, max_tokens=200)

    def annotate_clinical_text(self, text: str) -> str:
        """Annotate or extract key findings from clinical/literature text."""
        prompt = f"Extract key biomarker or clinical findings from: {text[:2000]}"
        return self.generate(prompt, max_tokens=200)

    def is_available(self) -> bool:
        """Return True if at least one backend (OpenAI or Hugging Face) is available."""
        if _openai_available():
            return True
        return self._get_pipeline() is not None

    def grounded_interpret_pipeline(
        self,
        genes: List[str],
        pipeline_summary: Optional[Dict[str, Any]] = None,
        extra_context: Optional[str] = None,
        max_tokens: int = 512,
        structured: bool = True,
    ) -> Dict[str, Any]:
        """
        Interpret biomarker results using bundled snippets, optional PubMed, and pipeline summary.
        When structured=True, asks the model for JSON keys summary, limitations, suggested_validation.
        """
        import json

        from app.observability.metrics import timed_llm
        from app.services.llm_grounding import retrieve_all_sources

        merged, matched_genes, api_sources = retrieve_all_sources(genes)
        context_blocks = []
        for s in merged:
            title = s.get("title") or s.get("id") or "snippet"
            body = s.get("text") or ""
            st = s.get("source_type", "corpus")
            context_blocks.append(f"[{st}::{title}]\n{body}")
        context_str = (
            "\n\n".join(context_blocks)
            if context_blocks
            else "(No matching grounding passages for these genes.)"
        )
        summary_str = json.dumps(pipeline_summary or {}, indent=2)[:4000]
        genes_str = ", ".join(str(g) for g in genes[:40])
        extra = (
            f"\n\nAdditional notes: {extra_context[:2000]}"
            if extra_context
            else ""
        )
        json_tail = ""
        if structured:
            json_tail = """

After the paragraphs, output exactly one JSON object (valid JSON, no markdown fences) with string fields:
{"summary": "...", "limitations": "...", "suggested_validation": "..."}
The JSON must appear on the last lines of your response."""
        user_prompt = f"""You assist with biomarker result interpretation for cancer research workflows.

Use ONLY the CONTEXT and PIPELINE SUMMARY. If the CONTEXT does not support a statement, say the knowledge sources provided do not cover it.

CONTEXT:
{context_str}

PIPELINE SUMMARY:
{summary_str}

TOP GENES FROM THIS RUN:
{genes_str}
{extra}

Write 2-4 short paragraphs covering: (1) biological themes suggested by the genes given the context; (2) cautious interpretation of statistical scores; (3) limitations and suggested validation. Do not fabricate citations or clinical recommendations beyond the context.{json_tail}"""
        system = "You are a careful biomedical assistant. Stay within the provided context."
        with timed_llm("interpret-grounded"):
            text = self.generate(user_prompt, system=system, max_tokens=max_tokens)

        structured_out: Dict[str, Any] = {}
        if structured:
            idx = text.rfind("{")
            if idx >= 0:
                try:
                    parsed = json.loads(text[idx:])
                    if isinstance(parsed, dict):
                        structured_out = {
                            "summary": parsed.get("summary", ""),
                            "limitations": parsed.get("limitations", ""),
                            "suggested_validation": parsed.get(
                                "suggested_validation", ""
                            ),
                        }
                except json.JSONDecodeError:
                    structured_out = {}

        return {
            "interpretation": text,
            "sources": api_sources,
            "matched_genes": matched_genes[:20],
            "structured": structured_out,
        }


def train_llm(
    train_data: Union[str, List[Dict[str, str]]],
    base_model_id: str = "google/flan-t5-base",
    output_dir: str = "models/llm_biomarker",
    num_epochs: int = 3,
    batch_size: int = 4,
    use_peft: bool = True,
) -> Dict[str, Any]:
    """
    Fine-tune an LLM on biomarker-related text (e.g. gene–disease pairs, summaries).
    Uses PEFT/LoRA when use_peft=True to keep resource use low.

    Args:
        train_data: Path to JSON/JSONL file with keys 'input' and 'target', or list of {"input": ..., "target": ...}
        base_model_id: Hugging Face model id
        output_dir: Where to save the fine-tuned model
        num_epochs: Training epochs
        batch_size: Per-device batch size
        use_peft: Use LoRA/PEFT for efficient fine-tuning

    Returns:
        Dict with training metrics and output path.
    """
    try:
        from datasets import Dataset
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as e:
        logger.error(
            "transformers and datasets required for LLM training: pip install transformers datasets"
        )
        return {"error": str(e), "success": False}

    try:
        if use_peft:
            from peft import LoraConfig, TaskType, get_peft_model
    except ImportError:
        use_peft = False
        logger.warning("peft not installed. Fine-tuning without LoRA. pip install peft")

    import json
    import os

    if isinstance(train_data, str):
        with open(train_data, "r", encoding="utf-8") as f:
            if train_data.endswith(".jsonl"):
                data = [json.loads(line) for line in f]
            else:
                data = json.load(f)
    else:
        data = list(train_data)

    if not data or not isinstance(data[0], dict):
        return {
            "error": "train_data must be a path to JSON/JSONL or list of {input, target}",
            "success": False,
        }

    inputs = [d.get("input", d.get("text", "")) for d in data]
    targets = [d.get("target", d.get("summary", "")) for d in data]
    dataset = Dataset.from_dict(
        {"input_ids": [], "labels": []}
    )  # placeholder; we'll use tokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(base_model_id)

    def tokenize_fn(examples):
        model_inputs = tokenizer(
            examples["input"],
            max_length=256,
            truncation=True,
            padding="max_length",
        )
        tgt = tokenizer(
            examples["target"],
            max_length=128,
            truncation=True,
            padding="max_length",
        )
        pad_id = getattr(tokenizer, "pad_token_id", None) or getattr(
            tokenizer, "eos_token_id", 0
        )
        labels = [[-100 if t == pad_id else t for t in seq] for seq in tgt["input_ids"]]
        model_inputs["labels"] = labels
        return model_inputs

    dataset = Dataset.from_dict({"input": inputs, "target": targets})
    dataset = dataset.map(tokenize_fn, batched=True, remove_columns=["input", "target"])

    if use_peft:
        peft_config = LoraConfig(
            task_type=TaskType.SEQ_2_SEQ_LM,
            r=8,
            lora_alpha=32,
            lora_dropout=0.1,
        )
        model = get_peft_model(model, peft_config)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        save_strategy="epoch",
        logging_steps=10,
        report_to="none",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )
    trainer.train()
    os.makedirs(output_dir, exist_ok=True)
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    return {
        "success": True,
        "output_dir": output_dir,
        "num_samples": len(data),
        "base_model": base_model_id,
        "use_peft": use_peft,
    }
