# R Installation in Docker

## Overview

The Dockerfile has been updated to properly install R and required R packages for bioinformatics analysis. This replaces the previous workaround using `RPY2_CFFI_MODE=ABI`.

## What's Installed

### R Base Installation
- `r-base`: R runtime
- `r-base-dev`: R development headers and tools

### R Development Libraries
- `libcurl4-openssl-dev`: For HTTP requests in R
- `libssl-dev`: SSL support
- `libxml2-dev`: XML parsing
- `libcairo2-dev`, `libharfbuzz-dev`, `libfribidi-dev`: Graphics rendering
- `libfreetype6-dev`, `libpng-dev`, `libtiff5-dev`, `libjpeg-dev`: Image format support

### R Packages Installed

#### Bioconductor Packages (via BiocManager)
- **DESeq2**: Differential expression analysis for RNA-seq
- **edgeR**: Empirical analysis of digital gene expression data
- **limma**: Linear models for microarray and RNA-seq data

#### CRAN Packages
- **survival**: Survival analysis
- **survminer**: Survival analysis visualization
- **ggplot2**: Data visualization
- **dplyr**: Data manipulation
- **RColorBrewer**: Color palettes
- **pheatmap**: Heatmap generation
- **VennDiagram**: Venn diagram creation

## Build Time

**Note**: Installing R and R packages will significantly increase Docker build time (approximately 10-15 additional minutes) because:
1. R base installation (~200MB)
2. R development libraries
3. Compilation of R packages from source (DESeq2, edgeR, etc.)

## Verification

After building, you can verify R installation:

```bash
# Check R version
docker compose exec backend R --version

# Test R package availability
docker compose exec backend R -e "library(DESeq2); library(edgeR); library(limma); cat('All packages loaded successfully\n')"

# Test rpy2 integration
docker compose exec backend python -c "import rpy2.robjects as ro; ro.r('library(DESeq2)'); print('rpy2 integration working')"
```

## Benefits

1. **Full R Functionality**: rpy2 can now use full R API, not just ABI mode
2. **Bioinformatics Tools**: DESeq2 and edgeR are industry-standard for RNA-seq analysis
3. **Benchmarking**: The benchmarking module can properly compare Python vs R implementations
4. **Statistical Analysis**: Access to comprehensive R statistical libraries

## Troubleshooting

If R package installation fails during build:
- Check Docker build logs for specific package errors
- Some packages may require additional system libraries
- Bioconductor packages may need specific R versions
