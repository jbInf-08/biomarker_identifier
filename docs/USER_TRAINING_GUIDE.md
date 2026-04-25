# Biomarker Identifier - User Training Guide

**Status (April 2026):** this document mixes **in-app behavior that exists today** with
**illustrative or aspirational** items (e.g. some collaboration and enterprise
support bullets). For guaranteed-accurate run instructions and ports, use
[HOW_TO_RUN.md](../HOW_TO_RUN.md) and [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). For
contact and issues, use the [README.md](../README.md) support section.

## Table of Contents

1. [Getting Started](#getting-started)
2. [System Overview](#system-overview)
3. [User Interface Navigation](#user-interface-navigation)
4. [Data Upload and Management](#data-upload-and-management)
5. [Analysis Configuration](#analysis-configuration)
6. [Results Interpretation](#results-interpretation)
7. [Report Generation](#report-generation)
8. [Advanced Features](#advanced-features)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

## Getting Started

### System Requirements

- **Web Browser**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Internet Connection**: Stable broadband connection recommended
- **Screen Resolution**: Minimum 1024x768, recommended 1920x1080
- **JavaScript**: Must be enabled
- **Cookies**: Must be enabled for session management

### Account Setup

1. **Registration**
   - Navigate to the registration page
   - Provide valid email address
   - Create strong password (minimum 8 characters)
   - Complete email verification

2. **Login**
   - Use registered email and password
   - Enable "Remember Me" for convenience
   - Use "Forgot Password" if needed

3. **Profile Configuration**
   - Update personal information
   - Set notification preferences
   - Configure analysis defaults

## System Overview

### Key Features

- **Multi-omics Data Analysis**: Gene expression, proteomics, metabolomics
- **Advanced Machine Learning**: Multiple algorithms and ensemble methods
- **Interactive Visualizations**: Dynamic plots and pathway networks
- **Clinical Annotation**: Integration with cancer databases
- **Collaborative Analysis**: Team-based research workflows
- **Real-time Monitoring**: Live analysis progress tracking

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   Database      │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   Celery        │    │   Redis Cache   │
│   (Real-time)   │    │   (Background)  │    │   (Sessions)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## User Interface Navigation

### Main Dashboard

The dashboard provides an overview of your analysis activities:

- **Recent Analyses**: Quick access to recent analysis runs
- **System Status**: Current system health and performance
- **Quick Actions**: Common tasks and shortcuts
- **Notifications**: Important updates and alerts

### Navigation Menu

#### Desktop Navigation
- **Dashboard**: Main overview page
- **Upload Data**: Data upload and management
- **Monitoring**: Real-time analysis monitoring
- **Results**: Analysis results and visualizations
- **Reports**: Report generation and export
- **Clinical**: Clinical annotation and interpretation

#### Mobile and responsive layout
- The web UI is **responsive**; a separate **mobile** app target also exists in the
  `mobile/` directory for native clients. Treat each as a separate surface when
  testing.

### User Profile

Access your profile to:
- Update personal information
- Change password
- Configure notification settings
- Manage API keys
- View usage statistics

## Data Upload and Management

### Supported File Formats

#### Gene expression data
- **CSV/TSV** (primary path in the current UI)
- Other scientific formats may be added in the future; rely on the upload page and release notes for your build

#### Sample Labels
- **CSV/TSV**: Sample ID and label columns
- **Excel**: .xlsx format with metadata
- **JSON**: Structured metadata format

### Upload Process

1. **Prepare your data (same as the in-app and manual guidance)**
   ```
   Expression matrix:
   - Rows: Genes
   - Columns: Samples
   - First column: gene identifiers; header row: sample IDs

   Labels file:
   - sample_id (or equivalent) must match expression column headers
   - class_label (or your outcome column) for groups
   ```

2. **Upload files**
   - Drag and drop or use the file picker
   - Follow the app’s size limits (see configuration; the default in code is on the order of 100MB for uploads, not 500MB)
   - Expression: CSV/TSV (see app and `USER_MANUAL.md` for supported types)

3. **Data Validation**
   - Automatic format detection
   - Data quality checks
   - Missing value identification
   - Outlier detection

4. **Data Preview**
   - Interactive data table
   - Statistical summaries
   - Quality metrics
   - Data distribution plots

### Data Management

#### Data Storage
- **Secure Storage**: Encrypted at rest
- **Access Control**: User-based permissions
- **Version Control**: Track data changes
- **Backup**: Automatic backups

#### Data Organization
- **Projects**: Group related analyses
- **Datasets**: Organize data files
- **Tags**: Categorize and search
- **Metadata**: Rich data descriptions

## Analysis Configuration

### Analysis Types

#### Classification Analysis
- **Purpose**: Distinguish between sample groups
- **Use Cases**: Disease vs. healthy, treatment response
- **Algorithms**: Random Forest, SVM, Neural Networks
- **Output**: Classification accuracy, feature importance

#### Survival Analysis
- **Purpose**: Predict time-to-event outcomes
- **Use Cases**: Patient survival, disease progression
- **Methods**: Cox regression, Kaplan-Meier
- **Output**: Survival curves, hazard ratios

#### Pathway Analysis
- **Purpose**: Identify biological pathways
- **Use Cases**: Functional interpretation
- **Databases**: KEGG, Reactome, GO
- **Output**: Pathway enrichment, network analysis

### Feature Selection

#### Methods Available
- **Statistical**: T-test, ANOVA, F-test
- **Information Theory**: Mutual information, entropy
- **Machine Learning**: LASSO, Random Forest, XGBoost
- **Dimensionality Reduction**: PCA, t-SNE, UMAP

#### Selection Criteria
- **P-value Threshold**: Statistical significance
- **Fold Change**: Biological relevance
- **Effect Size**: Practical significance
- **Multiple Testing**: FDR correction

### Cross-Validation

#### Types
- **K-Fold**: Standard cross-validation
- **Stratified**: Maintain class proportions
- **Leave-One-Out**: Exhaustive validation
- **Time Series**: Temporal validation

#### Parameters
- **Folds**: Number of cross-validation folds
- **Random State**: Reproducibility
- **Stratification**: Class balance
- **Scoring**: Performance metrics

## Results Interpretation

### Biomarker Results Table

#### Key Columns
- **Gene Symbol**: Official gene name
- **P-value**: Statistical significance
- **Fold Change**: Expression difference
- **FDR**: False discovery rate
- **Biomarker Score**: Combined relevance score
- **Clinical Relevance**: Clinical significance

#### Sorting and Filtering
- **Sort by**: Any column (ascending/descending)
- **Filter by**: P-value, fold change, score thresholds
- **Search**: Gene symbol or pathway
- **Export**: Selected results

### Visualizations

#### Volcano Plot
- **X-axis**: Log2 fold change
- **Y-axis**: -log10 p-value
- **Color**: Significance level
- **Interactive**: Click for gene details

#### Heatmap
- **Rows**: Genes (top biomarkers)
- **Columns**: Samples
- **Color**: Expression level
- **Clustering**: Hierarchical clustering

#### Pathway Network
- **Nodes**: Genes/proteins
- **Edges**: Interactions
- **Color**: Expression level
- **Size**: Importance score

### Statistical Interpretation

#### P-values
- **< 0.05**: Statistically significant
- **< 0.01**: Highly significant
- **< 0.001**: Very highly significant
- **Multiple Testing**: Use FDR correction

#### Fold Change
- **> 2**: 2-fold increase
- **< 0.5**: 2-fold decrease
- **Biological Relevance**: Consider context
- **Effect Size**: Practical significance

#### Biomarker Score
- **0.8-1.0**: High confidence
- **0.6-0.8**: Moderate confidence
- **0.4-0.6**: Low confidence
- **< 0.4**: Very low confidence

## Report Generation

### Report Types

#### PDF Report
- **Executive Summary**: Key findings
- **Methods**: Analysis parameters
- **Results**: Tables and figures
- **Discussion**: Interpretation
- **References**: Literature citations

#### HTML Report
- **Interactive**: Clickable elements
- **Responsive**: Mobile-friendly
- **Embedded**: Visualizations
- **Exportable**: Save as PDF

#### Excel Workbook
- **Multiple Sheets**: Organized data
- **Formatted**: Professional appearance
- **Charts**: Embedded visualizations
- **Metadata**: Analysis information

### Report Customization

#### Content Selection
- **Sections**: Choose report sections
- **Visualizations**: Select figures
- **Tables**: Include/exclude tables
- **Metadata**: Analysis details

#### Formatting Options
- **Logo**: Add organization logo
- **Colors**: Custom color schemes
- **Fonts**: Typography options
- **Layout**: Page arrangement

#### Export Options
- **Format**: PDF, HTML, Excel
- **Quality**: Resolution settings
- **Compression**: File size optimization
- **Security**: Password protection

## Advanced Features

### Collaboration and teams

**Current product:** per-user analysis runs, JWT auth, and optional `tenant_id` /
admin flows in the API. Full multi-user “workspaces” with real-time co-editing
are **not** guaranteed by this document — confirm with your deployment or the
[product roadmap](PRODUCT_ROADMAP.md) before training users on those workflows.

### API Integration

#### REST API
- **Authentication**: API key or OAuth
- **Endpoints**: Programmatic access
- **Rate Limiting**: Usage controls
- **Documentation**: Interactive docs

#### Webhook Support
- **Events**: Analysis completion
- **Notifications**: Status updates
- **Integration**: External systems
- **Customization**: Event filtering

### Advanced Analytics

#### Machine Learning
- **Ensemble Methods**: Multiple algorithms
- **Hyperparameter Tuning**: Optimization
- **Feature Engineering**: Custom features
- **Model Validation**: Cross-validation

#### Statistical Analysis
- **Multiple Testing**: FDR correction
- **Power Analysis**: Sample size
- **Effect Size**: Practical significance
- **Confidence Intervals**: Uncertainty

## Troubleshooting

### Common Issues

#### Upload Problems
- **File Size**: Check file size limits
- **Format**: Verify file format
- **Encoding**: UTF-8 encoding required
- **Headers**: Check column headers

#### Analysis Errors
- **Data Quality**: Missing values
- **Sample Size**: Insufficient samples
- **Class Balance**: Uneven groups
- **Computational**: Memory/time limits

#### Performance Issues
- **Browser**: Update browser
- **Cache**: Clear browser cache
- **Network**: Check connection
- **System**: Restart application

### Error Messages

#### Upload Errors
- **"Invalid file format"**: Check file type
- **"File too large"**: Reduce file size
- **"Missing headers"**: Add column headers
- **"Encoding error"**: Save as UTF-8

#### Analysis Errors
- **"Insufficient data"**: Add more samples
- **"Memory error"**: Reduce data size
- **"Timeout error"**: Increase time limit
- **"Convergence error"**: Adjust parameters

### Getting Help

#### Documentation
- **User Guide**: Comprehensive guide
- **API Docs**: Technical reference
- **Tutorials**: Step-by-step guides
- **FAQ**: Frequently asked questions

#### Support channels
- **GitHub Issues** and **Discussions** (see the repository README for links)
- **Email:** use the address listed in [README.md](../README.md) for maintainers

## Best Practices

### Data Preparation

#### Quality Control
- **Missing Values**: Handle appropriately
- **Outliers**: Identify and address
- **Normalization**: Standardize data
- **Batch Effects**: Account for batches

#### Documentation
- **Metadata**: Comprehensive descriptions
- **Version Control**: Track changes
- **Standards**: Follow conventions
- **Reproducibility**: Document parameters

### Analysis Design

#### Experimental Design
- **Sample Size**: Adequate power
- **Controls**: Appropriate controls
- **Randomization**: Reduce bias
- **Blinding**: Minimize bias

#### Statistical Considerations
- **Multiple Testing**: Correct for multiple comparisons
- **Effect Size**: Consider practical significance
- **Confidence Intervals**: Report uncertainty
- **Reproducibility**: Document methods

### Results Interpretation

#### Biological Relevance
- **Literature**: Check known functions
- **Pathways**: Consider biological context
- **Validation**: Independent validation
- **Clinical**: Translational relevance

#### Statistical Rigor
- **Significance**: Statistical significance
- **Effect Size**: Practical significance
- **Reproducibility**: Replication studies
- **Meta-analysis**: Combine studies

### Collaboration

#### Team Communication
- **Regular Meetings**: Progress updates
- **Documentation**: Share findings
- **Version Control**: Track changes
- **Feedback**: Peer review

#### Data Sharing
- **Standards**: Follow data standards
- **Privacy**: Protect sensitive data
- **Attribution**: Proper citations
- **Licensing**: Clear usage rights

---

## Additional Resources

### Training Materials
- **Video Tutorials**: Step-by-step videos
- **Webinars**: Live training sessions
- **Workshops**: Hands-on training
- **Certification**: User certification program

### Technical support

Use this repository’s documentation, API `/docs` on a running server, and the
[API_DOCUMENTATION.md](API_DOCUMENTATION.md) reference. There is no separate
commercial support portal implied by the repository layout.
