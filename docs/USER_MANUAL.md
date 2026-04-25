# Cancer Biomarker Identifier - User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Data Upload](#data-upload)
4. [Pipeline Configuration](#pipeline-configuration)
5. [Monitoring Analysis](#monitoring-analysis)
6. [Viewing Results](#viewing-results)
7. [Report Generation](#report-generation)
8. [Clinical Annotation](#clinical-annotation)
9. [Troubleshooting](#troubleshooting)
10. [FAQ](#faq)

## Introduction

The Cancer Biomarker Identifier is a comprehensive web application designed to identify, validate, and visualize cancer biomarkers using multi-omics data integration and machine learning approaches. This tool combines statistical analysis, machine learning, and biological context to provide robust biomarker discovery.

### Key Features

- **Multi-omics Data Integration**: Support for gene expression, proteomics, and clinical data
- **Statistical Analysis**: Differential expression analysis with multiple testing correction
- **Machine Learning**: Feature selection using filter, wrapper, and embedded methods
- **Explainability**: SHAP analysis for model interpretability
- **Pathway Analysis**: Gene set enrichment and over-representation analysis
- **Clinical Annotation**: Integration with cancer databases (COSMIC, ClinVar, OncoKB)
- **Comprehensive Reporting**: Publication-ready reports with visualizations
- **Reproducibility**: Complete pipeline documentation and run bundles

## Getting Started

### Prerequisites

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Expression data in TSV/CSV format
- Sample labels in TSV/CSV format
- Optional: Metadata file in YAML/JSON format

### Accessing the Application

1. **Local install:** use Docker Compose or a manual setup — see [HOW_TO_RUN.md](../HOW_TO_RUN.md) in the repo root.
2. **Web interface:** with Compose, the production-style frontend is usually on **http://localhost** (port 80). In dev (`npm start`), use **http://localhost:3000** with the API on port 8000.
3. **API:** base URL is `http://localhost:8000` (e.g. `/api/biomarkers/...` or `/api/v1/...`); see `/docs` when the server is running.

### First Time Setup

1. **Create account:** register in the app (or use an account your administrator created).
2. **Email verification** only applies if your deployment enables it (`is_verified` in the user model).
3. **Profile:** optional `name`, `institution`, and other fields from the **Settings** or profile flow.

## Data Upload

### Supported File Formats

- **Expression Data**: CSV, TSV, TXT files
- **Sample Labels**: CSV, TSV, TXT files
- **Metadata**: YAML, JSON files (optional)

### Data Requirements

#### Expression Data File
- **Format**: Genes as rows, samples as columns
- **First Column**: Gene identifiers (Gene Symbol, Ensembl ID, etc.)
- **Header Row**: Sample identifiers
- **Data Types**: Numeric values (log2-transformed recommended)
- **Missing Values**: Use empty cells or "NA"

Example:
```
Gene_Symbol,Sample_001,Sample_002,Sample_003
TP53,8.2,7.9,8.5
BRCA1,6.1,5.8,6.3
KRAS,7.4,7.2,7.6
```

#### Sample Labels File
- **Format**: Two columns minimum
- **First Column**: Sample identifiers (must match expression data)
- **Second Column**: Phenotype labels (e.g., "Tumor", "Normal")
- **Additional Columns**: Clinical variables (age, stage, etc.)

Example:
```
Sample_ID,Phenotype,Age,Stage
Sample_001,Tumor,65,III
Sample_002,Normal,62,NA
Sample_003,Tumor,58,II
```

### Upload Process

1. **Navigate to Data Upload**: Click "Data Upload" in the sidebar
2. **Select Files**: Drag and drop or click to select your files
3. **File Validation**: The system will validate file formats and content
4. **Preview Data**: Review a sample of your data before proceeding
5. **Configure Analysis**: Set analysis parameters (see Pipeline Configuration)

## Pipeline Configuration

### Analysis Parameters

#### Basic Settings
- **Run Name**: Descriptive name for your analysis
- **Normalization Method**: 
  - Log2: Log2 transformation
  - Z-score: Standardization
  - Quantile: Quantile normalization
  - TMM: Trimmed Mean of M-values

#### Statistical Analysis
- **Statistical Test**:
  - Welch t-test: For two-group comparisons
  - Wilcoxon: Non-parametric alternative
  - ANOVA: For multi-group comparisons
- **Significance Level (α)**: Default 0.05
- **Multiple Testing Correction**: Benjamini-Hochberg (FDR)

#### Machine Learning
- **Feature Selection Methods**:
  - Logistic Regression: Linear model with L1/L2 regularization
  - Random Forest: Ensemble method with feature importance
  - SVM: Support Vector Machine with RBF kernel
  - XGBoost: Gradient boosting with feature selection

#### Advanced Options
- **Cross-Validation Folds**: Number of CV folds (default: 5)
- **Random Seed**: For reproducibility
- **Quality Control**: Automatic filtering of low-quality samples/genes

### Configuration Examples

#### Standard Differential Expression Analysis
```json
{
  "normalization_method": "log2",
  "statistical_test": "welch_t",
  "alpha": 0.05,
  "ml_models": ["logistic_regression", "random_forest"]
}
```

#### Multi-group Analysis
```json
{
  "normalization_method": "quantile",
  "statistical_test": "anova",
  "alpha": 0.01,
  "ml_models": ["svm", "xgboost"]
}
```

## Monitoring Analysis

### Real-time Monitoring

1. **Navigate to Monitoring**: Click "Pipeline Monitoring" in the sidebar
2. **View Active Runs**: See all running analyses with progress bars
3. **Status Updates**: Real-time status updates every 5 seconds
4. **Progress Tracking**: Visual progress indicators for each pipeline step

### Pipeline Stages

1. **Data Validation**: File format and content validation
2. **Quality Control**: Sample and gene filtering
3. **Normalization**: Data transformation and scaling
4. **Statistical Analysis**: Differential expression analysis
5. **Machine Learning**: Feature selection and model training
6. **Clinical Annotation**: Database integration and annotation
7. **Report Generation**: Results compilation and visualization

### Status Indicators

- **Pending**: Analysis queued for processing
- **Running**: Analysis in progress
- **Completed**: Analysis finished successfully
- **Failed**: Analysis encountered an error
- **Cancelled**: Analysis was manually stopped

### Troubleshooting Failed Runs

1. **Check Error Messages**: Click on failed runs for detailed error information
2. **Review Data Quality**: Ensure data files meet requirements
3. **Check System Resources**: Verify sufficient memory and disk space
4. **Contact Support**: Submit error reports with run ID and error details

## Viewing Results

### Results Dashboard

1. **Navigate to Results**: Click "Results" in the sidebar
2. **Select Run**: Choose a completed analysis run
3. **View Summary**: Overview of analysis results and statistics

### Biomarker Table

- **Gene Symbol**: Gene identifier
- **P-value**: Statistical significance
- **Fold Change**: Effect size
- **Score**: Combined biomarker score
- **Description**: Gene function and relevance

### Interactive Visualizations

#### Volcano Plot
- **X-axis**: Log2 fold change
- **Y-axis**: -log10 p-value
- **Color**: Significance level
- **Interactive**: Click points for gene details

#### Heatmap
- **Rows**: Top significant genes
- **Columns**: Samples
- **Color**: Expression level
- **Clustering**: Hierarchical clustering of genes and samples

#### Pathway Enrichment
- **Bar Chart**: Enriched pathways
- **P-value**: Statistical significance
- **Gene Count**: Number of genes in pathway

### Export Options

- **CSV Export**: Download biomarker results
- **Visualization Export**: Save plots as PNG/PDF
- **Full Results**: Download complete analysis package

## Report Generation

### Report Types

#### Standard Report
- Analysis summary and methodology
- Top biomarkers with statistics
- Visualizations and plots
- Quality control metrics

#### Clinical Report
- Clinical relevance assessment
- Therapeutic implications
- Drug target information
- Evidence levels

#### Publication Report
- Detailed methodology
- Statistical analysis details
- Supplementary data
- Figure legends and captions

### Generating Reports

1. **Navigate to Reports**: Click "Reports" in the sidebar
2. **Select Run**: Choose a completed analysis
3. **Choose Format**: HTML or PDF
4. **Configure Content**: Select report sections and customizations
5. **Generate**: Click "Generate Report"
6. **Download**: Save or view the generated report

### Report Customization

- **Title**: Custom report title
- **Project Information**: Investigator, institution, funding
- **Content Selection**: Choose which sections to include
- **Visualization Options**: Customize plots and charts
- **Branding**: Add institutional logos and colors

## Clinical Annotation

### Available Databases

#### COSMIC (Catalogue of Somatic Mutations in Cancer)
- **Cancer Gene Census**: Curated list of cancer genes
- **Mutation Data**: Somatic mutations across cancer types
- **Frequency Information**: Mutation prevalence by cancer type
- **Clinical Significance**: Pathogenic vs. benign classifications

#### ClinVar
- **Clinical Variants**: Clinically relevant genetic variants
- **Clinical Significance**: Pathogenic, likely pathogenic, benign
- **Review Status**: Expert panel review levels
- **Condition Information**: Associated diseases and phenotypes

#### OncoKB
- **Cancer Genes**: Oncogenes and tumor suppressors
- **Therapeutic Implications**: Drug targets and treatments
- **Evidence Levels**: Clinical evidence classification
- **Biomarker Information**: Diagnostic and prognostic markers

### Annotation Process

1. **Automatic Annotation**: Runs automatically after biomarker identification
2. **Manual Annotation**: Select specific genes for detailed annotation
3. **Batch Annotation**: Annotate multiple genes simultaneously
4. **Custom Databases**: Upload custom annotation files

### Annotation Results

- **Clinical Relevance**: Evidence for clinical significance
- **Therapeutic Targets**: Available drugs and treatments
- **Biomarker Status**: Diagnostic/prognostic potential
- **Literature Evidence**: Supporting publications and studies

## Troubleshooting

### Common Issues

#### File Upload Problems
- **File Format**: Ensure files are in supported formats (CSV, TSV)
- **File Size**: Check file size limits (typically 100MB)
- **Encoding**: Use UTF-8 encoding for text files
- **Headers**: Ensure proper column headers

#### Analysis Failures
- **Data Quality**: Check for missing values and outliers
- **Sample Size**: Ensure sufficient sample size for statistical power
- **Group Balance**: Verify balanced group sizes
- **Gene Coverage**: Check for sufficient gene expression

#### Performance Issues
- **Large Datasets**: Consider data subsetting for initial analysis
- **Memory Usage**: Monitor system memory during analysis
- **Network**: Ensure stable internet connection
- **Browser**: Use modern, updated browsers

### Error Messages

#### "Invalid file format"
- Check file extension and content
- Ensure proper CSV/TSV formatting
- Verify column headers

#### "Insufficient data"
- Check sample size requirements
- Verify group balance
- Ensure sufficient gene coverage

#### "Analysis timeout"
- Reduce dataset size
- Check system resources
- Contact support for large datasets

### Getting Help

1. **Documentation**: Check this user manual and API documentation
2. **Community Forum**: Post questions in the user community
3. **Support Email**: Contact technical support
4. **Bug Reports**: Submit detailed bug reports with error logs

## FAQ

### General Questions

**Q: What types of data can I analyze?**
A: The system supports gene expression data (RNA-seq, microarray), proteomics data, and clinical data. Multi-omics integration is available for comprehensive analysis.

**Q: How long does an analysis take?**
A: Analysis time depends on dataset size and complexity. Typical analyses complete in 5-15 minutes for datasets with 1000-5000 genes and 50-200 samples.

**Q: Can I analyze multiple cancer types?**
A: Yes, the system supports multi-group comparisons and can handle multiple cancer types or subtypes in a single analysis.

**Q: Is my data secure?**
A: Yes, all data is encrypted in transit and at rest. User data is isolated and not shared between users.

### Technical Questions

**Q: What statistical methods are available?**
A: The system includes Welch t-test, Wilcoxon rank-sum test, ANOVA, and various machine learning methods including Random Forest, SVM, and XGBoost.

**Q: How are multiple testing corrections handled?**
A: The system uses Benjamini-Hochberg FDR correction by default, with options for other correction methods.

**Q: Can I customize the analysis pipeline?**
A: Yes, you can configure normalization methods, statistical tests, machine learning algorithms, and other parameters.

**Q: What visualization options are available?**
A: The system provides volcano plots, heatmaps, pathway enrichment plots, survival curves, and interactive dashboards.

### Data Questions

**Q: What file formats are supported?**
A: The system supports CSV, TSV, and TXT files for data input, with JSON and YAML for metadata.

**Q: How should I prepare my data?**
A: Expression data should have genes as rows and samples as columns. Sample labels should match sample identifiers in the expression data.

**Q: Can I use pre-processed data?**
A: Yes, the system can handle pre-processed data, but you may need to adjust normalization settings accordingly.

**Q: What about missing values?**
A: The system handles missing values through imputation or filtering, depending on the analysis configuration.

### Results Questions

**Q: How are biomarkers ranked?**
A: Biomarkers are ranked by a combined score incorporating statistical significance, effect size, and clinical relevance.

**Q: What is the biomarker score?**
A: The biomarker score is a composite metric combining p-value, fold change, and clinical annotation information.

**Q: Can I export results?**
A: Yes, you can export results in various formats including CSV, PDF reports, and visualization files.

**Q: How do I interpret the clinical annotations?**
A: Clinical annotations provide information about known cancer genes, therapeutic targets, and clinical significance from curated databases.

---

## Support and Contact

For additional support, please contact:

- **Technical Support**: support@biomarkerapp.com
- **Documentation**: docs@biomarkerapp.com
- **Community Forum**: https://community.biomarkerapp.com
- **GitHub Issues**: https://github.com/biomarkerapp/issues

---

*Last updated: January 2025*
*Version: 1.0.0*
