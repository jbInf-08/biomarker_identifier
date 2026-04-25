"""
Per-collector keyword arguments for smoke tests and dry-run documentation.

Keys are ``*_collector`` module stems (filename without ``.py``).
"""

from __future__ import annotations

from typing import Any, Dict

# Sites emphasized in product docs / demo (TCGA+GDC, GEO, COSMIC, ICGC, ClinVar, OncoKB, …)
COLLECTOR_SMOKE_KWARGS: Dict[str, Dict[str, Any]] = {
    "tcga_collector": {
        "data_type": "gene_expression",
        "cancer_type": "BRCA",
        "sample_limit": 2,
    },
    "geo_collector": {
        "search_term": "breast cancer",
        "data_type": "expression",
        "max_datasets": 3,
        "metadata_only": True,
    },
    "gdc_collector": {"data_type": "cases", "size": 15, "project": "TCGA-BRCA"},
    "cosmic_collector": {
        "data_type": "cancer_gene_census",
    },
    "icgc_collector": {
        "data_type": "bioproject_index",
        "sample_limit": 10,
        "term": "ICGC cancer",
    },
    "clinvar_collector": {
        "data_type": "genetic_variants",
        "gene_symbol": "BRCA1",
        "max_records": 25,
    },
    "oncokb_collector": {
        "data_type": "cancer_genes",
    },
    "ncbi_collector": {
        "data_type": "gene",
        "gene_symbol": "TP53",
        "max_ids": 5,
    },
    "pubmed_collector": {
        "data_type": "literature",
        "query": "cancer biomarker RNA",
        "max_records": 8,
    },
    "cbioportal_collector": {
        "data_type": "cancer_types",
    },
    "ccle_collector": {
        "data_type": "cell_line_data",
        "max_samples": 100,
    },
    "gdsc_collector": {
        "data_type": "drug_annotation",
        "max_rows": 150,
    },
    # Extended collectors (public_source_impl)
    "wisconsin_breast_cancer_collector": {},
    "brats_collector": {},
    "camelyon_collector": {},
    "cdc_collector": {"rows": 12},
    "ddsm_collector": {},
    "ega_collector": {"page_size": 8, "ena_scan_limit": 500},
    "firecloud_terra_collector": {"limit": 15},
    "tcia_glioblastoma_collector": {},
    "tcia_collector": {"max_collections": 500},
    "seer_collector": {"rows": 10},
    "rembrandt_collector": {"retmax": 6},
    "pathlaion_collector": {"rows": 10},
    "prostate_x_collector": {"size": 4},
    "pancancer_atlas_collector": {"page_size": 25},
    "nsclc_radiogenomics_collector": {},
    "nih_clinical_collector": {"page_size": 12},
    "nih_collector": {"limit": 12},
    "nci_collector": {"page_size": 12},
    "nci_60_collector": {"rows": 10},
    "ncdb_collector": {"rows": 10},
    "mimic_collector": {"max_rows": 150},
    "miccai_collector": {"limit": 12},
    "luna16_collector": {},
    "lidc_idri_collector": {},
    "kaggle_collector": {"limit": 12},
    "isic_collector": {"size": 5},
    "inbreast_collector": {"size": 4},
    "ham10000_collector": {"size": 4},
    "google_cloud_healthcare_collector": {},
}

PRIORITY_SOURCE_NAMES = [
    "TCGA",
    "GEO",
    "GDC",
    "COSMIC",
    "ICGC",
    "ClinVar",
    "OncoKB",
    "NCBI",
    "PubMed",
    "cBioPortal",
    "CCLE",
    "GDSC",
]
