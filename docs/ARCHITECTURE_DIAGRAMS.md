# System Architecture Diagrams
## Cancer Biomarker Identifier - Week 2 Progress

### Overall System Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        UI[React Frontend<br/>🚧 Planned]
        API_CLIENT[API Clients<br/>✅ Ready]
    end
    
    subgraph "Application Layer"
        FASTAPI[FastAPI Backend<br/>✅ Complete]
        CELERY[Celery Workers<br/>✅ Complete]
        FLOWER[Flower Monitor<br/>✅ Complete]
    end
    
    subgraph "Data Processing Layer"
        PIPELINE[Biomarker Pipeline<br/>✅ Complete]
        STATS[Statistical Analysis<br/>✅ Complete]
        ML[ML Components<br/>🚧 In Progress]
        QC[Quality Control<br/>🚧 In Progress]
    end
    
    subgraph "Data Layer"
        POSTGRES[(PostgreSQL<br/>✅ Complete)]
        REDIS[(Redis Cache<br/>✅ Complete)]
        FILES[File Storage<br/>✅ Complete]
    end
    
    subgraph "External Services"
        COSMIC[COSMIC API<br/>🚧 Planned]
        CLINVAR[ClinVar API<br/>🚧 Planned]
        ONCOKB[OncoKB API<br/>🚧 Planned]
    end
    
    subgraph "Monitoring & Infrastructure"
        PROMETHEUS[Prometheus<br/>✅ Complete]
        GRAFANA[Grafana<br/>✅ Complete]
        DOCKER[Docker Stack<br/>✅ Complete]
    end
    
    UI --> FASTAPI
    API_CLIENT --> FASTAPI
    FASTAPI --> PIPELINE
    FASTAPI --> POSTGRES
    FASTAPI --> REDIS
    CELERY --> PIPELINE
    CELERY --> POSTGRES
    PIPELINE --> STATS
    PIPELINE --> ML
    PIPELINE --> QC
    PIPELINE --> COSMIC
    PIPELINE --> CLINVAR
    PIPELINE --> ONCOKB
    STATS --> FILES
    ML --> FILES
    QC --> FILES
    PROMETHEUS --> GRAFANA
    DOCKER --> FASTAPI
    DOCKER --> CELERY
    DOCKER --> POSTGRES
    DOCKER --> REDIS
```

### Data Flow Architecture

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant FastAPI
    participant Celery
    participant Pipeline
    participant Database
    participant External
    
    User->>Frontend: Upload Data
    Frontend->>FastAPI: POST /api/data/upload
    FastAPI->>Database: Store metadata
    FastAPI->>Celery: Start analysis task
    Celery->>Pipeline: Execute biomarker analysis
    
    Pipeline->>Pipeline: Quality Control
    Pipeline->>Pipeline: Normalization
    Pipeline->>Pipeline: Statistical Analysis
    Pipeline->>Pipeline: ML Feature Selection
    Pipeline->>External: Annotate biomarkers
    External-->>Pipeline: Clinical annotations
    Pipeline->>Database: Store results
    Pipeline->>FastAPI: Update progress
    FastAPI->>Frontend: Real-time updates
    Frontend->>User: Display results
```

### Database Schema Architecture

```mermaid
erDiagram
    ANALYSIS_RUNS {
        uuid id PK
        string status
        timestamp created_at
        timestamp updated_at
        json configuration
        json progress
        json metrics
    }
    
    BIOMARKER_RESULTS {
        uuid id PK
        uuid run_id FK
        string gene_symbol
        float p_value
        float fold_change
        float effect_size
        json clinical_annotations
        json pathway_data
        json ml_features
    }
    
    EXPRESSION_DATA {
        uuid id PK
        uuid run_id FK
        string sample_id
        string gene_symbol
        float expression_value
        json quality_metrics
    }
    
    CLINICAL_DATA {
        uuid id PK
        uuid run_id FK
        string sample_id
        string phenotype
        json clinical_variables
        json survival_data
    }
    
    ANALYSIS_RUNS ||--o{ BIOMARKER_RESULTS : generates
    ANALYSIS_RUNS ||--o{ EXPRESSION_DATA : processes
    ANALYSIS_RUNS ||--o{ CLINICAL_DATA : processes
```

### Pipeline Processing Flow

```mermaid
flowchart TD
    START([Start Analysis]) --> UPLOAD[Data Upload]
    UPLOAD --> VALIDATE[Data Validation]
    VALIDATE --> QC[Quality Control]
    QC --> NORM[Normalization]
    NORM --> BATCH[Batch Correction]
    BATCH --> STATS[Statistical Analysis]
    STATS --> ML[ML Feature Selection]
    ML --> ANNOTATE[Clinical Annotation]
    ANNOTATE --> PATHWAY[Pathway Analysis]
    PATHWAY --> REPORT[Report Generation]
    REPORT --> END([Analysis Complete])
    
    QC --> QC_FAIL{QC Passed?}
    QC_FAIL -->|No| QC_REPORT[QC Report]
    QC_REPORT --> END
    
    STATS --> STATS_FAIL{Stats Valid?}
    STATS_FAIL -->|No| STATS_REPORT[Stats Report]
    STATS_REPORT --> END
    
    ML --> ML_FAIL{ML Valid?}
    ML_FAIL -->|No| ML_REPORT[ML Report]
    ML_REPORT --> END
```

### Deployment Architecture

```mermaid
graph TB
    subgraph "Development Environment"
        DEV_APP[biomarker-dev:8001]
        DEV_DB[(PostgreSQL Dev)]
        DEV_REDIS[(Redis Dev)]
        DEV_MONITOR[Grafana Dev]
    end
    
    subgraph "Production Environment"
        PROD_APP[biomarker-app:8000]
        PROD_DB[(PostgreSQL Prod)]
        PROD_REDIS[(Redis Prod)]
        PROD_MONITOR[Grafana Prod]
        PROD_WORKERS[Celery Workers]
    end
    
    subgraph "External Services"
        COSMIC_API[COSMIC API]
        CLINVAR_API[ClinVar API]
        ONCOKB_API[OncoKB API]
    end
    
    subgraph "Monitoring Stack"
        PROMETHEUS[Prometheus]
        GRAFANA[Grafana Dashboard]
        FLOWER[Flower Task Monitor]
    end
    
    DEV_APP --> DEV_DB
    DEV_APP --> DEV_REDIS
    DEV_APP --> DEV_MONITOR
    
    PROD_APP --> PROD_DB
    PROD_APP --> PROD_REDIS
    PROD_APP --> PROD_WORKERS
    PROD_WORKERS --> PROD_DB
    
    PROD_APP --> COSMIC_API
    PROD_APP --> CLINVAR_API
    PROD_APP --> ONCOKB_API
    
    PROMETHEUS --> GRAFANA
    PROMETHEUS --> FLOWER
```

### Component Status Legend

- ✅ **Complete**: Fully implemented and tested
- 🚧 **In Progress**: Partially implemented
- ❌ **Not Started**: Planned but not yet implemented
- 🔄 **Planned**: Scheduled for future implementation

### Technology Stack Details

| Layer | Technology | Version | Status | Purpose |
|-------|------------|---------|--------|---------|
| **Frontend** | React | 18.x | 🚧 Planned | User interface |
| **Backend** | FastAPI | 0.104+ | ✅ Complete | API server |
| **Database** | PostgreSQL | 15+ | ✅ Complete | Primary database |
| **Cache** | Redis | 7+ | ✅ Complete | Caching & task queue |
| **Task Queue** | Celery | 5.3+ | ✅ Complete | Background processing |
| **Container** | Docker | 24+ | ✅ Complete | Containerization |
| **Monitoring** | Prometheus | 2.45+ | ✅ Complete | Metrics collection |
| **Visualization** | Grafana | 10+ | ✅ Complete | Monitoring dashboard |
| **ML** | scikit-learn | 1.3+ | 🚧 In Progress | Machine learning |
| **Stats** | SciPy | 1.11+ | ✅ Complete | Statistical analysis |

### Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        CORS[CORS Protection<br/>✅ Implemented]
        RATE[Rate Limiting<br/>✅ Implemented]
        VALID[Input Validation<br/>✅ Implemented]
        AUTH[Authentication<br/>🚧 Planned]
        ENCRYPT[Data Encryption<br/>✅ Implemented]
    end
    
    subgraph "Data Protection"
        ANON[Data Anonymization<br/>✅ Implemented]
        AUDIT[Audit Logging<br/>✅ Implemented]
        RETENTION[Data Retention<br/>✅ Implemented]
        BACKUP[Backup & Recovery<br/>✅ Implemented]
    end
    
    subgraph "Infrastructure Security"
        ENV[Environment Config<br/>✅ Implemented]
        SECRETS[Secret Management<br/>✅ Implemented]
        NETWORK[Network Security<br/>✅ Implemented]
        CONTAINER[Container Security<br/>✅ Implemented]
    end
```

### Performance Architecture

```mermaid
graph TB
    subgraph "Performance Optimization"
        CACHE[Redis Caching<br/>✅ Implemented]
        POOL[Connection Pooling<br/>✅ Implemented]
        ASYNC[Async Processing<br/>✅ Implemented]
        COMPRESS[Data Compression<br/>✅ Implemented]
    end
    
    subgraph "Scalability"
        HORIZONTAL[Horizontal Scaling<br/>✅ Implemented]
        LOAD_BALANCE[Load Balancing<br/>🚧 Planned]
        AUTO_SCALE[Auto Scaling<br/>🚧 Planned]
        CDN[CDN Integration<br/>🚧 Planned]
    end
    
    subgraph "Monitoring"
        METRICS[Performance Metrics<br/>✅ Implemented]
        ALERTS[Alerting System<br/>✅ Implemented]
        PROFILING[Code Profiling<br/>✅ Implemented]
        OPTIMIZATION[Auto Optimization<br/>🚧 Planned]
    end
```

---

## Architecture Decisions

### 1. Microservices Architecture
**Decision**: Implemented modular microservices architecture
**Rationale**: Enables independent scaling, easier maintenance, and technology diversity
**Status**: ✅ Implemented

### 2. Event-Driven Processing
**Decision**: Used Celery for asynchronous task processing
**Rationale**: Handles long-running analysis tasks without blocking the API
**Status**: ✅ Implemented

### 3. Container-First Deployment
**Decision**: Docker-based deployment with Docker Compose
**Rationale**: Ensures consistency across environments and simplifies deployment
**Status**: ✅ Implemented

### 4. Database Design
**Decision**: PostgreSQL with JSON fields for flexible data storage
**Rationale**: Balances structured data with flexibility for multi-omics data
**Status**: ✅ Implemented

### 5. Monitoring Integration
**Decision**: Prometheus + Grafana for comprehensive monitoring
**Rationale**: Provides observability for production deployment
**Status**: ✅ Implemented

---

**Last Updated**: April 2026 (align diagrams with `docs/PRODUCT_ROADMAP.md` and `docker-compose.yml` when making structural changes)  
**Version**: 1.0.0  
**Status**: Week 2 - Core Architecture Complete
