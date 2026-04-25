# System Handover Documentation

## Overview

This document provides a **template** for system handover. **Placeholders and example
hostnames** (e.g. `biomarker-identifier.com`, team inboxes) are not maintained as live
facts for this open-source repository. For the actual repo URL, support options, and
maintainer contact, use the **Support** section in the root [README.md](../README.md).
Authoritative run instructions: [HOW_TO_RUN.md](../HOW_TO_RUN.md) and
[PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md).

## System Information

### System Name
**Cancer Biomarker Identifier**

### System Purpose
A comprehensive web application for identifying and analyzing cancer biomarkers from multi-omics data using advanced machine learning and statistical methods.

### System status
**Repository / build** — the application is an actively developed FastAPI + React
codebase. Whether it is “production ready” depends on your own deployment, tests,
and compliance sign-off.

### Current version
The API reports **1.0.0** in `app.main:app` (see `backend/app/main.py`); align
marketing or release version numbers in your own release process.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                 Application Layer                          │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Frontend      │   Backend API   │   WebSocket Service     │
│   (React)       │   (FastAPI)     │   (Real-time)           │
└─────────────────┴─────────────────┴─────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                 Service Layer                              │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Celery        │   Redis         │   Monitoring            │
│   (Background)   │   (Cache)       │   (Prometheus)         │
└─────────────────┴─────────────────┴─────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                 Data Layer                                  │
├─────────────────┬─────────────────┬─────────────────────────┤
│   PostgreSQL    │   File Storage  │   Log Storage           │
│   (Database)    │   (Data)        │   (Logs)               │
└─────────────────┴─────────────────┴─────────────────────────┘
```

### Technology Stack

#### Frontend
- **Framework**: React 18.x
- **UI Library**: Tailwind CSS
- **Charts**: Recharts
- **State Management**: Context API
- **Build Tool**: Create React App

#### Backend
- **Framework**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL 13+
- **Cache**: Redis 6+
- **Task Queue**: Celery
- **ORM**: SQLAlchemy
- **API Documentation**: OpenAPI/Swagger

#### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Kubernetes
- **Monitoring**: Prometheus, Grafana
- **Logging**: Structured JSON logging
- **CI/CD**: GitHub Actions (if configured)

## System Components

### Core Services

#### 1. Frontend Service
- **Purpose**: User interface and interactions
- **Port**: 3000 (development), 80 (production)
- **Health Check**: `/health`
- **Key Features**:
  - Data upload and management
  - Analysis monitoring
  - Results visualization
  - Report generation

#### 2. Backend API Service
- **Purpose**: RESTful API and business logic
- **Port**: 8000
- **Health Check**: `/health`, `/api/health`
- **Key Features**:
  - Biomarker analysis pipeline
  - Machine learning models
  - Clinical annotation
  - Report generation

#### 3. Database Service
- **Purpose**: Data persistence
- **Type**: PostgreSQL
- **Port**: 5432
- **Database Name**: biomarker_db
- **Key Features**:
  - User management
  - Analysis runs storage
  - Biomarker results
  - Clinical annotations

#### 4. Cache Service
- **Purpose**: Caching and session management
- **Type**: Redis
- **Port**: 6379
- **Key Features**:
  - API response caching
  - Session storage
  - Task queue broker

#### 5. Background Workers
- **Purpose**: Asynchronous task processing
- **Type**: Celery Workers
- **Key Features**:
  - Long-running analyses
  - Background data processing
  - Report generation
  - Email notifications

#### 6. Monitoring Service
- **Purpose**: System monitoring and alerting
- **Type**: Prometheus + Grafana
- **Ports (when included in `docker-compose.prod.yml`):** 9090 (Prometheus), 3000 (Grafana on the host in that file)
- **Key Features**:
  - System metrics collection
  - Performance monitoring
  - Alert management
  - Dashboard visualization

## Deployment Information

### Production Environment

#### Infrastructure
- **Cloud Provider**: [Specify if applicable]
- **Region**: [Specify if applicable]
- **Kubernetes Cluster**: [Specify if applicable]

#### Service URLs
Fill in your deployment’s **public URL**, **API /docs path**, and **Grafana** (if used). Local development defaults are in [HOW_TO_RUN.md](../HOW_TO_RUN.md).

#### Access Credentials
⚠️ **IMPORTANT**: Store credentials securely. Update this section with actual credentials.

- **Database Admin**: [Credentials in secure vault]
- **Redis Access**: [Credentials in secure vault]
- **Monitoring Access**: [Credentials in secure vault]
- **Application Admin**: [Credentials in secure vault]

### Deployment Process

#### Initial deployment
```bash
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier
cp production.env.example .env   # then edit for your environment
docker compose -f docker-compose.prod.yml up -d
# Migrations: use the one-shot `migrate` service pattern from the compose file, or `docker compose run --rm migrate` as in HOW_TO_RUN
```

#### Update deployment
```bash
git pull
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose run --rm migrate
```

Service names and the exact `migrate` invocation follow [docker-compose.prod.yml](../docker-compose.prod.yml) in the repository you deploy.

## Operational procedures

### Daily Operations

#### Morning Checklist
1. ✅ Check system health dashboard
2. ✅ Review overnight alerts
3. ✅ Verify backup completion
4. ✅ Check service status
5. ✅ Review performance metrics

#### Monitoring Tasks
- Monitor system resources (CPU, memory, disk)
- Review application logs for errors
- Check database performance
- Monitor cache hit rates
- Review user activity

### Weekly Operations

#### Maintenance Tasks
- Run weekly maintenance script
- Verify backup integrity
- Review security alerts
- Update documentation
- Performance optimization review

#### Reporting
- Generate weekly system report
- Review user activity statistics
- Analyze performance trends
- Document issues and resolutions

### Monthly Operations

#### Comprehensive Review
- Full system backup
- Security audit
- Performance analysis
- Capacity planning
- Documentation updates

## Configuration Management

### Environment Variables

#### Required Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/biomarker_db

# Redis
REDIS_URL=redis://host:6379/0

# Security
SECRET_KEY=your-secret-key-256-bits
JWT_SECRET_KEY=your-jwt-secret-key

# External APIs
COSMIC_API_KEY=your_cosmic_api_key
ONCOKB_API_KEY=your_oncokb_api_key
PUBMED_API_KEY=your_pubmed_api_key
```

#### Optional Variables
```bash
# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Monitoring
ALERT_WEBHOOK_URL=https://your-webhook-url
GRAFANA_ADMIN_PASSWORD=your-grafana-password
```

### Configuration Files

#### Key Configuration Files
- `docker-compose.prod.yml` - Production Docker configuration
- `k8s/` - Kubernetes deployment manifests
- `monitoring/` - Monitoring configuration
- `.env` - Environment variables (not in version control)

## Backup and Recovery

### Backup Procedures

#### Automated Backups
- **Database Backup**: Daily at 2:00 AM
- **File Backup**: Daily at 3:00 AM
- **Full Backup**: Weekly on Sunday at 1:00 AM
- **Retention**: 30 days for daily, 90 days for weekly

#### Manual Backup
```bash
# Database backup
./scripts/backup_database.sh

# Full backup
./scripts/full_backup.sh
```

### Recovery Procedures

#### Database Recovery
```bash
# Restore database from backup
./scripts/restore_database.sh backup_file.sql.gz
```

#### Full System Recovery
1. Provision new infrastructure
2. Restore configuration files
3. Restore database backup
4. Restore file system backup
5. Start services
6. Verify functionality

## Monitoring and Alerting

### Monitoring Dashboards

#### Grafana Dashboards
- **System Overview**: System-wide metrics
- **Application Performance**: API and application metrics
- **Database Performance**: Database-specific metrics
- **Infrastructure**: Infrastructure metrics

### Alerting Rules

#### Critical Alerts
- Database down
- Redis unavailable
- Application service failure
- Disk space > 90%
- Memory usage > 95%

#### Warning Alerts
- CPU usage > 80%
- Memory usage > 85%
- Slow query response times
- High error rates
- Cache hit rate < 70%

### Alert notifications
Configure in your own monitoring (email, webhooks, PagerDuty, etc.); the repo only ships example Prometheus / Grafana wiring in `docker-compose.prod.yml` when you enable those services.

## Troubleshooting Guide

### Common Issues

See `docs/ONGOING_MAINTENANCE.md` for detailed troubleshooting procedures.

#### Quick Reference
- **Service not starting**: Check logs, verify dependencies
- **Database connection issues**: Verify credentials, check network
- **High memory usage**: Review background tasks, optimize queries
- **Slow performance**: Check database indexes, review cache settings

## Security Information

### Security Practices

#### Access Control
- Role-based access control (RBAC)
- JWT authentication
- Session management
- API rate limiting

#### Data Protection
- Encryption at rest
- TLS for data in transit
- Secure credential storage
- Regular security audits

#### Security Monitoring
- Audit logging
- Failed login tracking
- Suspicious activity detection
- Regular vulnerability scanning

### Security contacts
List your own security and on-call contacts; do not use placeholder inboxes in production.

## Documentation

### Key Documents

#### User Documentation
- `docs/USER_MANUAL.md` - Complete user manual
- `docs/USER_TRAINING_GUIDE.md` - Training materials
- `docs/USER_GUIDE.md` - Quick start guide

#### Technical Documentation
- `docs/API_DOCUMENTATION.md` - API reference
- `docs/ARCHITECTURE_DIAGRAMS.md` - Architecture diagrams
- `docs/DEPLOYMENT_GUIDE.md` - Deployment instructions
- `docs/SYSTEM_ADMINISTRATION_GUIDE.md` - Administration guide

#### Maintenance Documentation
- `docs/MAINTENANCE_ROADMAP.md` - Maintenance planning
- `docs/ONGOING_MAINTENANCE.md` - Ongoing maintenance procedures

### Code Documentation
- Inline code documentation
- API endpoint documentation (OpenAPI)
- Database schema documentation

## Contact information

Use the root [README.md](../README.md) (Support / Community) for the maintained GitHub
and email contact points. Replace that section in **your** fork or internal handover
copy with your organization’s people and on-call rotation.

## Knowledge Transfer Checklist

### Infrastructure
- [ ] Access to all systems and services
- [ ] Credentials securely stored
- [ ] Monitoring dashboards accessible
- [ ] Backup procedures documented
- [ ] Recovery procedures tested

### Codebase
- [ ] Repository access
- [ ] Code review process understood
- [ ] Development environment setup
- [ ] Testing procedures known
- [ ] Deployment process documented

### Operations
- [ ] Daily operations understood
- [ ] Weekly maintenance procedures known
- [ ] Monthly tasks documented
- [ ] Monitoring alerts configured
- [ ] Troubleshooting guides reviewed

### Documentation
- [ ] All documentation reviewed
- [ ] System architecture understood
- [ ] API documentation accessible
- [ ] User guides reviewed
- [ ] Maintenance procedures documented

## Next Steps for New Team

### Immediate Actions (Week 1)
1. Review all documentation
2. Set up access to all systems
3. Review current system status
4. Understand operational procedures
5. Meet with outgoing team

### Short-term Actions (Month 1)
1. Shadow daily operations
2. Perform maintenance tasks under supervision
3. Review and update documentation
4. Understand monitoring and alerting
5. Review backup and recovery procedures

### Long-term Actions (Quarter 1)
1. Take ownership of daily operations
2. Optimize maintenance procedures
3. Enhance monitoring and alerting
4. Review and improve documentation
5. Plan system enhancements

## Additional Resources

### External resources
- **Source:** https://github.com/jbInf-08/biomarker_identifier
- In-repo documentation: `docs/` and `README.md` (this repository is the documentation “portal” unless you host a site separately)

### Training Resources
- **System Administration Training**: Available on-demand
- **Development Training**: Available quarterly
- **User Training**: Available monthly

## Appendix

### A. Glossary
- **Biomarker**: A measurable indicator of biological state
- **Multi-omics**: Integration of multiple omics data types
- **Clinical Annotation**: Adding clinical context to biomarkers
- **Pipeline**: Automated analysis workflow

### B. Acronyms
- **API**: Application Programming Interface
- **RBAC**: Role-Based Access Control
- **JWT**: JSON Web Token
- **REST**: Representational State Transfer
- **CI/CD**: Continuous Integration/Continuous Deployment

### C. Version history
Record releases in your own changelog or `git tag` notes; the FastAPI `app` version
string in code is a separate, deploy-time concern.

---

**Last updated:** April 2026  
**Maintainer:** follow the practices in [ONGOING_MAINTENANCE.md](ONGOING_MAINTENANCE.md) and [MAINTENANCE_ROADMAP.md](MAINTENANCE_ROADMAP.md).

