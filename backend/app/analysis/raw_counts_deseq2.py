"""
Optional differential expression on raw count matrices via R (DESeq2 / edgeR).

Enable with ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2=true, R with DESeq2 installed, and
``pip install -r backend/requirements-optional-deseq2.txt``.
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from app.core.config import settings


def _validate_raw_counts_inputs(counts: pd.DataFrame, coldata: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Production-safe validation for DESeq2/edgeR inputs."""
    if counts.empty:
        raise ValueError("counts matrix is empty")
    if coldata.empty:
        raise ValueError("coldata is empty")
    common = counts.columns.intersection(coldata.index)
    if len(common) < 4:
        raise ValueError("Need at least 4 aligned samples between counts and coldata")
    counts = counts[common]
    coldata = coldata.loc[common]
    if "condition" not in coldata.columns:
        raise ValueError("coldata must include a 'condition' column for design ~ condition")
    # Ensure integer-like non-negative counts.
    num = counts.apply(pd.to_numeric, errors="coerce")
    if num.isna().any().any():
        raise ValueError("counts matrix contains non-numeric values")
    if (num < 0).any().any():
        raise ValueError("counts matrix contains negative values")
    rounded = num.round().astype(int)
    groups = coldata["condition"].astype(str).value_counts()
    if groups.shape[0] < 2:
        raise ValueError("condition must contain at least 2 groups")
    if (groups < 2).any():
        raise ValueError("each condition group must have at least 2 replicates")
    return rounded, coldata


def run_deseq2(
    counts: pd.DataFrame,
    *,
    coldata: pd.DataFrame,
) -> pd.DataFrame:
    """
    Run DESeq2 on a counts matrix (genes × samples) and sample metadata.

    Expects ``coldata`` to include a ``condition`` column (two or more groups).
    """
    if not getattr(settings, "ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2", False):
        raise RuntimeError(
            "Set ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2=true and install R + DESeq2 + rpy2"
        )
    try:
        import rpy2.robjects as ro
        from rpy2.robjects import pandas2ri
        from rpy2.robjects.conversion import localconverter
        from rpy2.robjects.packages import importr
    except ImportError as e:
        raise RuntimeError(
            "rpy2 is not installed; use backend/requirements-optional-deseq2.txt"
        ) from e

    importr("DESeq2")

    counts, coldata = _validate_raw_counts_inputs(counts, coldata)

    with localconverter(ro.default_converter + pandas2ri.converter):
        ro.globalenv["count_df"] = counts
        ro.globalenv["coldata_df"] = coldata

    ro.r(
        """
        library(DESeq2)
        coldata_df <- as.data.frame(coldata_df)
        count_df <- as.matrix(count_df)
        if (!all(rownames(coldata_df) == colnames(count_df))) {
          stop("coldata row names must match count matrix columns")
        }
        dds <- DESeqDataSetFromMatrix(
          countData = count_df,
          colData = coldata_df,
          design = ~ condition
        )
        dds <- DESeq(dds)
        res <- results(dds)
        res_df <- as.data.frame(res)
        """
    )
    res_df = ro.r("res_df")
    with localconverter(ro.default_converter + pandas2ri.converter):
        out = ro.conversion.rpy2py(res_df)
    if not isinstance(out, pd.DataFrame):
        out = pd.DataFrame(out)
    return out


def run_edger(
    counts: pd.DataFrame,
    *,
    coldata: pd.DataFrame,
) -> pd.DataFrame:
    """
    Quasi-likelihood DE with edgeR (genes × samples counts, ``condition`` in coldata).
    """
    if not getattr(settings, "ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2", False):
        raise RuntimeError(
            "Set ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2=true and install R + edgeR + rpy2"
        )
    try:
        import rpy2.robjects as ro
        from rpy2.robjects import pandas2ri
        from rpy2.robjects.conversion import localconverter
        from rpy2.robjects.packages import importr
    except ImportError as e:
        raise RuntimeError(
            "rpy2 is not installed; use backend/requirements-optional-deseq2.txt"
        ) from e

    importr("edgeR")

    counts, coldata = _validate_raw_counts_inputs(counts, coldata)

    with localconverter(ro.default_converter + pandas2ri.converter):
        ro.globalenv["count_df"] = counts
        ro.globalenv["coldata_df"] = coldata

    ro.r(
        """
        library(edgeR)
        coldata_df <- as.data.frame(coldata_df)
        count_df <- as.matrix(count_df)
        if (!all(rownames(coldata_df) == colnames(count_df))) {
          stop("coldata row names must match count matrix columns")
        }
        group <- factor(coldata_df$condition)
        y <- DGEList(counts = count_df, group = group)
        y <- calcNormFactors(y)
        design <- model.matrix(~group)
        y <- estimateDisp(y, design)
        fit <- glmQLFit(y, design)
        qlf <- glmQLFTest(fit, coef = 2)
        res_df <- as.data.frame(topTags(qlf, n = nrow(count_df))$table)
        """
    )
    res_df = ro.r("res_df")
    with localconverter(ro.default_converter + pandas2ri.converter):
        out = ro.conversion.rpy2py(res_df)
    if not isinstance(out, pd.DataFrame):
        out = pd.DataFrame(out)
    return out


def run_deseq2_or_edger_stub(
    counts_path: str,
    coldata_path: str,
    *,
    method: str = "deseq2",
) -> Dict[str, Any]:
    """Load TSVs and run DESeq2 or edgeR."""
    counts = pd.read_csv(counts_path, sep="\t", index_col=0)
    coldata = pd.read_csv(coldata_path, sep="\t", index_col=0)
    m = method.lower()
    if m == "deseq2":
        res = run_deseq2(counts, coldata=coldata)
        sort_col = "padj" if "padj" in res.columns else res.columns[0]
    elif m in ("edger", "edge_r", "edgeR"):
        res = run_edger(counts, coldata=coldata)
        sort_col = "FDR" if "FDR" in res.columns else res.columns[0]
    else:
        raise ValueError("method must be deseq2 or edger")
    top = res.sort_values(sort_col, na_position="last").head(50)
    return {
        "method": m,
        "n_genes": int(len(res)),
        "top_rows": top.reset_index().to_dict(orient="records"),
    }


def deseq2_available() -> bool:
    if not getattr(settings, "ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2", False):
        return False
    try:
        import rpy2  # noqa: F401
    except ImportError:
        return False
    return True
