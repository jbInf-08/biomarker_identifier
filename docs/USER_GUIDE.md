# Cancer Biomarker Identifier - User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Data Preparation](#data-preparation)
4. [Running the Pipeline](#running-the-pipeline)
5. [Understanding Results](#understanding-results)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [FAQ](#faq)

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

### Supported Study Designs

- **Binary Classification**: Tumor vs. Normal, Responder vs. Non-Responder
- **Multi-class Classification**: Molecular subtypes, cancer stages
- **Continuous Outcomes**: Survival analysis, drug response (future)

## Getting Started

### Prerequisites

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Expression data in TSV/CSV format
- Sample labels in TSV/CSV format
- Optional: Metadata file in YAML/JSON format

### Accessing the Application

1. **Local install:** use Docker or run backend + frontend on the host — see [HOW_TO_RUN.md](../HOW_TO_RUN.md).
2. **Web UI:** with the default Docker Compose stack, open **http://localhost** (frontend on port 80, API on **http://localhost:8000**). In dev, the React app is typically **http://localhost:3000**.
3. **API:** `http://localhost:8000/api/...` (versioned copies under `/api/v1/...` and `/api/v2/...`); use **/docs** for the live OpenAPI list.

### First Steps

1. **Upload Data**: Prepare your expression and labels files
2. **Configure Pipeline**: Set analysis parameters
3. **Run Analysis**: Execute the biomarker identification pipeline
4. **Review Results**: Explore biomarkers, statistics, and visualizations
5. **Generate Report**: Create publication-ready reports

## Data Preparation

### Expression Data Format

Your expression data should be formatted as a matrix with:
- **Rows**: Genes (Ensembl IDs or gene symbols)
- **Columns**: Samples (sample IDs as headers)
- **Values**: Expression values (counts, TPM, FPKM, etc.)

**Example (TSV format):**
```tsv
Gene	SAMPLE_001	SAMPLE_002	SAMPLE_003	SAMPLE_004
TP53	1250	980	1100	890
BRCA1	850	920	780	950
BRCA2	650	720	680	750
EGFR	450	380	520	410
KRAS	320	280	350	290
```

**Requirements:**
- File format: TSV or CSV
- Gene identifiers: Ensembl IDs (preferred) or gene symbols
- Sample identifiers: Unique sample IDs
- Missing values: Use empty cells or NA
- File size: Up to 100MB

### Labels Data Format

Your labels file should contain:
- **sample_id**: Must match expression data column headers
- **class_label**: Primary outcome variable
- **Additional columns**: Covariates (age, gender, stage, etc.)

**Example (TSV format):**
```tsv
sample_id	class_label	age	gender	stage
SAMPLE_001	TUMOR	45	F	II
SAMPLE_002	TUMOR	52	M	III
SAMPLE_003	NORMAL	48	F	NA
SAMPLE_004	NORMAL	51	M	NA
```

**Requirements:**
- File format: TSV or CSV
- Sample IDs: Must match expression data exactly
- Class labels: Binary (e.g., TUMOR/NORMAL) or multi-class
- Missing values: Use NA or empty cells
- File size: Up to 10MB

### Metadata (Optional)

A metadata file can provide additional context:

**Example (YAML format):**
```yaml
project_name: "BRCA Biomarker Study"
investigator: "Dr. Jane Smith"
institution: "Cancer Research Institute"
species: "Homo sapiens"
genome_build: "GRCh38"
data_type: "RNA-seq"
normalization: "log2"
consent_note: "All samples collected with informed consent"
publication_doi: "10.1000/example"
```

### Data Quality Checklist

Before uploading, ensure your data meets these criteria:

- [ ] **Sample Overlap**: At least 80% of samples present in both files
- [ ] **Gene Coverage**: At least 100 genes with expression data
- [ ] **Sample Size**: At least 10 samples per group
- [ ] **Missing Data**: Less than 20% missing values per gene
- [ ] **Data Types**: Consistent data types (numeric for expression)
- [ ] **Identifiers**: Consistent gene and sample identifiers

## Running the Pipeline

### Step 1: Data Upload

1. **Navigate to Data Upload Tab**
   - Click on the "Data Upload" tab in the main interface

2. **Upload Expression File**
   - Click "Choose File" or drag and drop your expression file
   - Supported formats: TSV, CSV
   - Maximum size: 100MB

3. **Upload Labels File**
   - Click "Choose File" or drag and drop your labels file
   - Ensure sample IDs match expression data

4. **Upload Metadata (Optional)**
   - Upload metadata file for additional context
   - Supported formats: YAML, JSON

5. **Validate Data**
   - Click "Validate Data" to check format and compatibility
   - Review validation results and address any issues

### Step 2: Pipeline Configuration

Configure the analysis parameters:

#### Basic Settings
- **Run Name**: Descriptive name for your analysis
- **Normalization Method**: Choose appropriate transformation
  - `log2`: For count data (recommended for RNA-seq)
  - `log10`: Alternative log transformation
  - `z_score`: Standardization
  - `quantile`: Quantile normalization

#### Statistical Analysis
- **Statistical Methods**: Choose appropriate tests
  - `t_test`: Welch's t-test (binary outcomes)
  - `wilcoxon`: Wilcoxon rank-sum test (non-parametric)
  - `anova`: One-way ANOVA (multi-class)
  - `kruskal`: Kruskal-Wallis test (non-parametric)

#### Machine Learning
- **Selection Methods**: Choose feature selection algorithms
  - `logistic_regression`: LASSO regularization
  - `random_forest`: Random Forest importance
  - `svm`: Support Vector Machine with RFE
  - `xgboost`: XGBoost importance

#### Advanced Settings
- **Number of Features**: Target number of biomarkers (default: 100)
- **Stability Bootstraps**: Number of bootstrap iterations (default: 100)
- **Cross-validation Folds**: Number of CV folds (default: 5)

### Step 3: Start Analysis

1. **Review Configuration**
   - Double-check all settings before starting

2. **Start Pipeline**
   - Click "Start Pipeline" to begin analysis
   - Note the Run ID for tracking

3. **Monitor Progress**
   - Switch to "Pipeline Monitoring" tab
   - Track progress and current step
   - Estimated completion time will be displayed

## Understanding Results

### Pipeline Monitoring

The monitoring interface shows:
- **Current Status**: Running, completed, or failed
- **Progress**: Percentage completion
- **Current Step**: Active pipeline stage
- **Estimated Completion**: Time remaining

### Results Overview

Once completed, results are organized into several sections:

#### 1. Biomarker List

**Top Biomarkers Table:**
- **Gene**: Gene identifier
- **Final Score**: Combined statistical and ML evidence (0-1)
- **Final Rank**: Overall ranking position
- **Statistical Evidence**: Significant in statistical tests
- **ML Evidence**: Selected by machine learning methods

**Summary Cards:**
- **Total Biomarkers**: Number of identified biomarkers
- **Statistically Significant**: Biomarkers with p < 0.05
- **ML Selected**: Biomarkers selected by ML methods
- **High Confidence**: Biomarkers with score > 0.7

#### 2. Statistical Analysis

**Volcano Plot:**
- X-axis: Log2 fold change
- Y-axis: -log10(p-value)
- Points: Individual genes
- Significance threshold: FDR < 0.05

**Statistical Results Table:**
- **Gene**: Gene identifier
- **Log2FC**: Log2 fold change
- **P-value**: Raw p-value
- **FDR**: False discovery rate
- **Effect Size**: Cohen's d or similar

#### 3. Machine Learning Results

**Feature Importance Plot:**
- Bar chart of feature importance scores
- Ranked by selection frequency

**Consensus Analysis:**
- **Consensus Score**: Agreement across methods (0-1)
- **Selection Count**: Number of methods selecting each gene
- **Methods**: List of selecting algorithms

#### 4. Model Performance

**Performance Metrics:**
- **Accuracy**: Overall prediction accuracy
- **Precision**: Positive predictive value
- **Recall**: Sensitivity
- **F1 Score**: Harmonic mean of precision and recall
- **ROC-AUC**: Area under ROC curve
- **PR-AUC**: Area under precision-recall curve

**Cross-validation Results:**
- Mean and standard deviation across folds
- Performance stability assessment

#### 5. SHAP Analysis

**Global Analysis:**
- **Feature Importance**: Overall feature contributions
- **Summary Plot**: SHAP value distribution
- **Bar Plot**: Mean absolute SHAP values

**Local Analysis:**
- **Waterfall Plot**: Individual sample predictions
- **Dependence Plot**: Feature interaction effects

#### 6. Pathway Analysis

**GSEA Results:**
- **Enriched Pathways**: Significantly enriched gene sets
- **NES**: Normalized enrichment score
- **FDR**: False discovery rate
- **Leading Edge**: Core genes in enrichment

**ORA Results:**
- **Over-represented Pathways**: Pathways with gene overlap
- **P-value**: Statistical significance
- **Odds Ratio**: Enrichment strength

#### 7. Gene Annotation

**Clinical Context:**
- **Cancer Information**: Mutation frequency, cancer types
- **Clinical Significance**: Pathogenic variants, evidence levels
- **Expression Patterns**: Tissue and cancer expression

**Evidence Cards:**
- **Basic Info**: Gene name, chromosome, description
- **Cancer Relevance**: Oncogenicity, mutation spectrum
- **Clinical Impact**: Therapeutic implications

## Advanced Features

### Custom Analysis

#### Model Training
1. **Select Features**: Choose genes for model training
2. **Configure Model**: Set model type and parameters
3. **Train Model**: Execute training with cross-validation
4. **Evaluate Performance**: Review metrics and plots

#### SHAP Analysis
1. **Choose Model**: Select trained model for analysis
2. **Set Parameters**: Configure analysis type and samples
3. **Generate Plots**: Create explainability visualizations
4. **Interpret Results**: Understand feature contributions

#### Pathway Analysis
1. **Select Genes**: Choose biomarker genes for analysis
2. **Choose Databases**: Select gene set databases
3. **Run Analysis**: Execute GSEA and ORA
4. **Review Results**: Explore enriched pathways

### Report Generation

#### Report Types
- **HTML Report**: Interactive web report
- **PDF Report**: Publication-ready document

#### Report Content
- **Executive Summary**: Key findings and metrics
- **Methods**: Detailed methodology
- **Results**: Comprehensive results with figures
- **Discussion**: Biological interpretation
- **Appendices**: Technical details and data

#### Customization
- **Report Title**: Custom title for your analysis
- **Include Appendices**: Technical details and methods
- **Include Figures**: All generated visualizations
- **Include Tables**: Complete results tables

### Data Export

#### Available Formats
- **CSV**: Comma-separated values
- **TSV**: Tab-separated values
- **JSON**: Structured data format
- **Excel**: Microsoft Excel format

#### Export Options
- **Biomarker List**: Ranked biomarker table
- **Statistical Results**: Differential expression results
- **ML Results**: Feature selection results
- **Pathway Results**: Enrichment analysis results
- **Complete Results**: All pipeline outputs

## Troubleshooting

### Common Issues

#### Data Upload Problems

**Issue**: "File format not supported"
- **Solution**: Ensure file is TSV or CSV format
- **Check**: File extension and delimiter consistency

**Issue**: "Sample IDs don't match"
- **Solution**: Verify sample IDs are identical in both files
- **Check**: Case sensitivity and whitespace

**Issue**: "Missing values detected"
- **Solution**: Review data quality and missing value patterns
- **Check**: Consider imputation or filtering

#### Pipeline Errors

**Issue**: "Pipeline failed during normalization"
- **Solution**: Check for negative or infinite values
- **Check**: Ensure appropriate transformation method

**Issue**: "No significant biomarkers found"
- **Solution**: Review statistical thresholds and data quality
- **Check**: Consider different statistical methods

**Issue**: "Memory error during analysis"
- **Solution**: Reduce dataset size or use sampling
- **Check**: Close other applications to free memory

#### Performance Issues

**Issue**: "Analysis taking too long"
- **Solution**: Reduce number of features or bootstrap iterations
- **Check**: Dataset size and computational resources

**Issue**: "Results not loading"
- **Solution**: Refresh page or restart analysis
- **Check**: Browser compatibility and internet connection

### Error Messages

#### Validation Errors
- **"Invalid file format"**: Check file type and structure
- **"Missing required columns"**: Ensure all required columns present
- **"Data type mismatch"**: Verify numeric data in expression file

#### Processing Errors
- **"Insufficient data"**: Ensure minimum requirements met
- **"Convergence failed"**: Try different parameters or methods
- **"Out of memory"**: Reduce dataset size or use sampling

#### System Errors
- **"Service unavailable"**: Check server status
- **"Timeout error"**: Reduce analysis complexity
- **"Connection lost"**: Check network connection

### Getting Help

#### Self-Service
1. **Check Documentation**: Review this guide and API docs
2. **Validate Data**: Use built-in validation tools
3. **Review Logs**: Check error messages and warnings

#### Support Channels
- **GitHub Issues**: Report bugs and request features
- **Email Support**: Contact support team
- **Community Forum**: Ask questions and share experiences

## Best Practices

### Data Preparation

#### Expression Data
- **Use Ensembl IDs**: Preferred for gene identification
- **Normalize Appropriately**: Choose correct transformation
- **Check Quality**: Review missing data and outliers
- **Document Sources**: Include data source and processing steps

#### Labels Data
- **Ensure Consistency**: Match sample IDs exactly
- **Balance Classes**: Aim for balanced group sizes
- **Include Covariates**: Add relevant clinical variables
- **Document Definitions**: Clearly define outcome variables

#### Metadata
- **Be Comprehensive**: Include all relevant project information
- **Use Standards**: Follow established metadata schemas
- **Document Changes**: Track data processing modifications

### Analysis Design

#### Study Design
- **Define Objectives**: Clear research questions
- **Choose Methods**: Appropriate statistical and ML approaches
- **Plan Validation**: Include validation strategies
- **Consider Confounders**: Account for batch effects and covariates

#### Parameter Selection
- **Start Conservative**: Use default parameters initially
- **Iterate Gradually**: Make small parameter changes
- **Document Choices**: Record parameter selection rationale
- **Validate Results**: Check biological plausibility

### Result Interpretation

#### Statistical Significance
- **Multiple Testing**: Consider FDR correction
- **Effect Sizes**: Evaluate practical significance
- **Confidence Intervals**: Assess uncertainty
- **Replication**: Validate in independent datasets

#### Biological Relevance
- **Literature Review**: Check known associations
- **Pathway Analysis**: Explore functional context
- **Clinical Impact**: Assess therapeutic potential
- **Mechanistic Understanding**: Consider biological mechanisms

#### Machine Learning
- **Cross-validation**: Ensure robust performance
- **Feature Stability**: Check selection consistency
- **Model Interpretability**: Use SHAP analysis
- **Performance Metrics**: Consider multiple evaluation criteria

### Reporting

#### Documentation
- **Complete Methods**: Document all analysis steps
- **Parameter Settings**: Record all configuration choices
- **Data Sources**: Cite data origins and processing
- **Limitations**: Acknowledge study limitations

#### Visualization
- **Clear Figures**: Use appropriate plot types
- **Consistent Formatting**: Maintain visual consistency
- **Informative Labels**: Include clear axis labels and legends
- **Publication Quality**: Ensure high-resolution outputs

#### Reproducibility
- **Version Control**: Track software and data versions
- **Run Bundles**: Save complete analysis artifacts
- **Environment Documentation**: Record computational environment
- **Code Sharing**: Share analysis scripts when possible

## FAQ

### General Questions

**Q: What types of data does the application support?**
A: The application supports gene expression data (RNA-seq, microarray), proteomics data, and clinical data in TSV/CSV formats.

**Q: How long does an analysis typically take?**
A: Analysis time depends on dataset size: small datasets (<1,000 genes, <50 samples) take 1-2 minutes, medium datasets take 5-10 minutes, and large datasets take 10-30 minutes.

**Q: Can I use my own reference data?**
A: Currently, the application uses built-in reference databases. Custom reference data support is planned for future versions.

**Q: Is my data secure?**
A: Security depends on how the deployment is configured (TLS, access control, backups, retention). Analysis runs and uploads are tied to your account in the database; ask your administrator for the retention and privacy policy for your environment.

### Technical Questions

**Q: What file formats are supported?**
A: Expression and labels data: TSV, CSV. Metadata: YAML, JSON. Reports: HTML, PDF.

**Q: How do I handle missing data?**
A: The application can handle missing data up to 20% per gene. Consider imputation or filtering for higher missing rates.

**Q: Can I run multiple analyses simultaneously?**
A: Yes, you can start multiple pipeline runs. Each run gets a unique ID for tracking.

**Q: How do I export my results?**
A: Results can be exported in CSV, TSV, JSON, or Excel formats from the results interface.

### Analysis Questions

**Q: Which statistical test should I use?**
A: Use t-test for normally distributed data, Wilcoxon for non-parametric data, ANOVA for multi-class comparisons.

**Q: How many features should I select?**
A: Start with 100 features and adjust based on your research needs and computational resources.

**Q: What does the consensus score mean?**
A: The consensus score (0-1) indicates agreement across multiple feature selection methods. Higher scores indicate more robust selection.

**Q: How do I interpret SHAP values?**
A: SHAP values show feature contributions to predictions. Positive values increase prediction probability, negative values decrease it.

### Biological Questions

**Q: How do I know if my biomarkers are biologically relevant?**
A: Check literature associations, pathway enrichment, and clinical annotation. High-scoring biomarkers with known cancer associations are more likely to be relevant.

**Q: What databases are used for annotation?**
A: The application integrates with COSMIC, ClinVar, OncoKB, and other cancer databases for comprehensive annotation.

**Q: How do I validate my findings?**
A: Use independent datasets, experimental validation, and cross-validation. Consider external validation cohorts when available.

**Q: Can I compare results across different studies?**
A: Yes, you can compare biomarker lists and pathway enrichments across different analyses using the export and comparison features.

### Support Questions

**Q: How do I report a bug?**
A: Use the GitHub Issues page to report bugs with detailed descriptions and error messages.

**Q: Can I request new features?**
A: Yes, feature requests are welcome through GitHub Issues or email support.

**Q: Is there training available?**
A: Training materials and tutorials are available in the documentation and GitHub repository.

**Q: How do I cite this tool?**
A: Please cite the application using the DOI and citation information provided in the documentation.

---

For additional support and questions, please refer to the API documentation or contact the support team.
