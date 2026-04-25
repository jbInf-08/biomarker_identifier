# Real Data Test Fixtures

This directory contains **real-world datasets** used for testing. All tests use actual data - no synthetic or artificial data.

## Data Sources

### Expression Data
- **TCGA samples** - Real cancer gene expression data
- **GEO datasets** - Publicly available expression datasets
- **Real clinical studies** - Anonymized patient data

### Clinical Data
- **Real survival data** - Actual patient outcomes
- **Clinical annotations** - Real biomarker associations
- **Treatment responses** - Actual therapy outcomes

### Edge Cases
- **Single sample studies** - Real pilot studies
- **Imbalanced datasets** - Real rare disease studies
- **Missing data patterns** - Real data quality issues

## Data Format

All data files follow standard formats:
- Expression: CSV with genes as rows, samples as columns
- Clinical: CSV with samples as rows, clinical variables as columns
- Metadata: JSON with study information

## Usage

```python
from tests.fixtures.real_data import load_real_expression_data, load_real_clinical_data

# Use real data in tests
expression_data = load_real_expression_data("tcga_brca_sample")
clinical_data = load_real_clinical_data("tcga_brca_clinical")
```

## Privacy & Ethics

- All data is **publicly available** or **anonymized**
- No personally identifiable information (PII)
- Complies with data sharing agreements
- Data sources documented in each file
