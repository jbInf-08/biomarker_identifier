# Biomarker Identifier - System Administration Guide

**Status (April 2026):** many procedures below are **reference patterns** (firewall, Certbot, generic Nginx). The **authoritative** compose layout, ports, and Celery command for this repository are in `docker-compose.yml`, `docker-compose.prod.yml`, and [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). The `User` model uses `email`, `name`, and `role` (not a separate `username` or `is_admin` column).

## Table of Contents

1. [System Overview](#system-overview)
2. [Installation and Setup](#installation-and-setup)
3. [Configuration Management](#configuration-management)
4. [User Management](#user-management)
5. [Security Administration](#security-administration)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Backup and Recovery](#backup-and-recovery)
8. [Performance Optimization](#performance-optimization)
9. [Troubleshooting](#troubleshooting)
10. [Disaster Recovery](#disaster-recovery)

## System Overview

### Architecture Components

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

### System Requirements

#### Minimum Requirements
- **CPU**: 4 cores, 2.4 GHz
- **RAM**: 8 GB
- **Storage**: 100 GB SSD
- **Network**: 100 Mbps
- **OS**: Ubuntu 20.04 LTS, CentOS 8, RHEL 8

#### Recommended Requirements
- **CPU**: 8 cores, 3.0 GHz
- **RAM**: 32 GB
- **Storage**: 500 GB NVMe SSD
- **Network**: 1 Gbps
- **OS**: Ubuntu 22.04 LTS, CentOS 9, RHEL 9

#### Production Requirements
- **CPU**: 16+ cores, 3.5 GHz
- **RAM**: 64+ GB
- **Storage**: 1+ TB NVMe SSD (RAID 1)
- **Network**: 10 Gbps
- **OS**: Ubuntu 22.04 LTS, RHEL 9

## Installation and Setup

### Prerequisites

#### System Dependencies
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    curl \
    wget \
    git \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Node.js (for development)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Python (for development)
sudo apt install -y python3.9 python3.9-pip python3.9-venv
```

#### External Services
- **SMTP Server**: For email notifications
- **S3 Storage**: For file storage (optional)
- **External APIs**: COSMIC, ClinVar, OncoKB, PubMed

### Installation Process

#### 1. Clone repository
```bash
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier
```

#### 2. Environment configuration
```bash
# See env.template and production.env.example in the repo root; copy what your environment needs.
cp production.env.example .env
# or for backend-only: cp backend/.env.example backend/.env
```

#### 3. Database setup
First-time full stack: see [HOW_TO_RUN.md](../HOW_TO_RUN.md) (`docker compose up -d --build`).

Migrations only (Postgres must be healthy):

```bash
docker compose run --rm migrate
```

**Create an admin user** (one-off, from `backend/` with the venv activated, or in the API container; change password immediately):

```python
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user_model import User

db = SessionLocal()
u = User(
    email="admin@example.com",
    name="Admin",
    hashed_password=get_password_hash("change-me-now"),
    role="admin",
    is_active=True,
    is_verified=True,
)
db.add(u)
db.commit()
db.close()
```

#### 4. Application deployment
```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

Use `BIOMARKER_DOCKER_USERNAME` and built images as described in the prod compose file.

#### 5. SSL certificate (example; paths depend on your host)
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
# Mount the resulting cert paths into the nginx service per nginx/nginx.prod.conf, then:
docker compose -f docker-compose.prod.yml restart nginx
```

## Configuration Management

### Environment Variables

#### Core Configuration
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/biomarker_db
POSTGRES_DB=biomarker_db
POSTGRES_USER=biomarker_user
POSTGRES_PASSWORD=secure_password

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-256-bits
DEBUG=False
LOG_LEVEL=INFO

# External APIs
COSMIC_API_KEY=your_cosmic_api_key
ONCOKB_API_KEY=your_oncokb_api_key
PUBMED_API_KEY=your_pubmed_api_key
```

#### Email Configuration
```bash
# SMTP Settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@biomarker-identifier.com
```

#### Storage Configuration
```bash
# Local Storage
DATA_DIR=/opt/biomarker-identifier/data
UPLOAD_DIR=/opt/biomarker-identifier/uploads
EXPORT_DIR=/opt/biomarker-identifier/exports
LOG_DIR=/var/log/biomarker-identifier

# S3 Storage (Optional)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_BUCKET=biomarker-data
AWS_S3_REGION=us-west-2
```

### Service Configuration

#### Nginx Configuration
```nginx
# /etc/nginx/sites-available/biomarker-identifier
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=upload:10m rate=1r/s;
    
    # API endpoints
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # File uploads
    location /api/upload {
        limit_req zone=upload burst=5 nodelay;
        client_max_body_size 500M;
        proxy_pass http://backend:8000;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
    
    # Frontend
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### PostgreSQL Configuration
```sql
-- /etc/postgresql/13/main/postgresql.conf
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

## User Management

### User Roles and Permissions

#### Admin Users
- **Full Access**: All system functions
- **User Management**: Create, modify, delete users
- **System Configuration**: Modify system settings
- **Monitoring**: Access system monitoring
- **Backup/Restore**: Database operations

#### Regular Users
- **Data Upload**: Upload and manage data
- **Analysis**: Run analyses and view results
- **Reports**: Generate and export reports
- **Collaboration**: Share with team members

#### Read-Only Users
- **View Only**: Access to results and reports
- **No Upload**: Cannot upload data
- **No Analysis**: Cannot run analyses
- **Export**: Can export results

### User Administration

#### Create a user
Use the [admin API](API_DOCUMENTATION.md) or a one-off script with `User` fields
`email`, `name`, `hashed_password`, and `role` (see `app.models.user_model`).

#### Example: list and deactivate
```text
# Prefer SQLAlchemy session code against app.models.user_model.User by email, not "username"
```

### Authentication and Authorization

#### Password Policies
- **Minimum Length**: 8 characters
- **Complexity**: Mix of letters, numbers, symbols
- **Expiration**: 90 days (configurable)
- **History**: Cannot reuse last 5 passwords

#### Session Management
- **Session Timeout**: 24 hours (configurable)
- **Concurrent Sessions**: Maximum 3 per user
- **Remember Me**: 30 days (configurable)
- **Logout**: Automatic on timeout

## Security Administration

### Network Security

#### Firewall Configuration
```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 5432/tcp   # PostgreSQL (internal only)
sudo ufw deny 6379/tcp   # Redis (internal only)
```

#### SSL/TLS Configuration
```nginx
# Strong SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
```

### Application Security

#### Input Validation
- **File Upload**: Type and size validation
- **API Input**: Schema validation
- **SQL Injection**: Parameterized queries
- **XSS Protection**: Output encoding

#### Data Encryption
- **At Rest**: Database encryption
- **In Transit**: TLS 1.2+
- **Sensitive Data**: Field-level encryption
- **Backups**: Encrypted backups

### Security Monitoring

#### Audit Logging
```python
# Enable audit logging
AUDIT_LOG_ENABLED=True
AUDIT_LOG_LEVEL=INFO
AUDIT_LOG_FILE=/var/log/biomarker-identifier/audit.log
```

#### Security Alerts
- **Failed Logins**: Multiple failed attempts
- **Suspicious Activity**: Unusual access patterns
- **Data Exports**: Large data downloads
- **System Changes**: Configuration modifications

## Monitoring and Maintenance

### System Monitoring

#### Health checks
```bash
# Liveness / readiness
curl -f http://localhost:8000/health/ready
curl -f http://localhost:8000/api/status

# Detailed JSON (v1 and v2 both exist)
curl -s http://localhost:8000/api/v1/system/health

# Database
docker compose exec postgres pg_isready -U postgres

# Redis
docker compose exec redis redis-cli ping

# Disk space
df -h

# Memory usage
free -h

# CPU usage
top -bn1 | grep "Cpu(s)"
```

#### Monitoring Dashboard
- **Prometheus**: Metrics collection
- **Grafana**: Visualization
- **Alertmanager**: Alerting
- **Custom Dashboards**: Application metrics

### Log Management

#### Log Rotation
```bash
# /etc/logrotate.d/biomarker-identifier
/var/log/biomarker-identifier/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 biomarker biomarker
    postrotate
        docker compose -f /opt/biomarker-identifier/docker-compose.prod.yml restart backend
    endscript
}
```

#### Log Analysis
```bash
# Error analysis
grep -i error /var/log/biomarker-identifier/application.log | tail -100

# Performance analysis
grep "slow query" /var/log/biomarker-identifier/application.log

# Security analysis
grep -i "failed login" /var/log/biomarker-identifier/audit.log
```

### Regular Maintenance

#### Daily Tasks
```bash
#!/bin/bash
# daily_maintenance.sh

# Check service status
docker compose -f docker-compose.prod.yml ps

# Check disk space
df -h | awk '$5 > 80 {print $0}'

# Check memory usage
free -h | awk 'NR==2{printf "Memory Usage: %s/%s (%.2f%%)\n", $3,$2,$3*100/$2 }'

# Check log files
tail -100 /var/log/biomarker-identifier/application.log | grep -i error

# Database maintenance
docker compose exec postgres psql -U postgres -d biomarker_db -c "VACUUM ANALYZE;"
```

#### Weekly Tasks
```bash
#!/bin/bash
# weekly_maintenance.sh

# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean Docker images
docker system prune -f

# Database backup
./scripts/backup_database.sh

# Log rotation
sudo logrotate -f /etc/logrotate.d/biomarker-identifier

# Security updates
sudo unattended-upgrades
```

#### Monthly Tasks
```bash
#!/bin/bash
# monthly_maintenance.sh

# Full system backup
./scripts/full_backup.sh

# Security audit
./scripts/security_audit.sh

# Performance analysis
./scripts/performance_analysis.sh

# Certificate renewal check
certbot certificates
```

## Backup and Recovery

### Database Backup

#### Automated Backup
```bash
#!/bin/bash
# backup_database.sh

BACKUP_DIR="/opt/backups/biomarker-identifier"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="biomarker_db_${DATE}.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
docker compose exec postgres pg_dump -U postgres biomarker_db > $BACKUP_DIR/$BACKUP_FILE

# Compress backup
gzip $BACKUP_DIR/$BACKUP_FILE

# Remove old backups (keep 30 days)
find $BACKUP_DIR -name "biomarker_db_*.sql.gz" -mtime +30 -delete

echo "Database backup completed: $BACKUP_DIR/$BACKUP_FILE.gz"
```

#### Backup Restoration
```bash
#!/bin/bash
# restore_database.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Stop application
docker compose -f docker-compose.prod.yml stop backend

# Restore database
gunzip -c $BACKUP_FILE | docker compose exec -T postgres psql -U postgres biomarker_db

# Start application
docker compose -f docker-compose.prod.yml start backend

echo "Database restored from: $BACKUP_FILE"
```

### File System Backup

#### Data Backup
```bash
#!/bin/bash
# backup_data.sh

BACKUP_DIR="/opt/backups/biomarker-identifier"
DATE=$(date +%Y%m%d_%H%M%S)
DATA_DIR="/opt/biomarker-identifier/data"

# Create backup
tar -czf $BACKUP_DIR/data_${DATE}.tar.gz -C $DATA_DIR .

# Upload to S3 (if configured)
if [ ! -z "$AWS_S3_BUCKET" ]; then
    aws s3 cp $BACKUP_DIR/data_${DATE}.tar.gz s3://$AWS_S3_BUCKET/backups/
fi

echo "Data backup completed: $BACKUP_DIR/data_${DATE}.tar.gz"
```

### Disaster Recovery

#### Recovery Procedures
1. **System Recovery**
   - Restore from backup
   - Reconfigure services
   - Verify functionality

2. **Data Recovery**
   - Restore database
   - Restore file system
   - Validate data integrity

3. **Service Recovery**
   - Start core services
   - Verify connectivity
   - Test functionality

## Performance Optimization

### Database Optimization

#### Index Optimization
```sql
-- Create indexes for better performance
CREATE INDEX CONCURRENTLY idx_analysis_runs_user_id ON analysis_runs(user_id);
CREATE INDEX CONCURRENTLY idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX CONCURRENTLY idx_biomarker_results_run_id ON biomarker_results(run_id);
CREATE INDEX CONCURRENTLY idx_biomarker_results_gene_symbol ON biomarker_results(gene_symbol);
CREATE INDEX CONCURRENTLY idx_user_activities_user_id ON user_activities(user_id);
CREATE INDEX CONCURRENTLY idx_user_activities_timestamp ON user_activities(timestamp);

-- Analyze tables for better query planning
ANALYZE analysis_runs;
ANALYZE biomarker_results;
ANALYZE user_activities;
```

#### Query Optimization
```sql
-- Monitor slow queries
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Update statistics
ANALYZE;

-- Vacuum tables
VACUUM ANALYZE;
```

### Application Optimization

#### Caching Configuration
```python
# Redis caching
CACHE_TTL = 3600  # 1 hour
CACHE_MAX_SIZE = 1000
CACHE_STRATEGY = "LRU"
```

#### Connection Pooling
```python
# Database connection pooling
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 30
DATABASE_POOL_TIMEOUT = 30
DATABASE_POOL_RECYCLE = 3600
```

### System Optimization

#### Resource Limits
```yaml
# docker-compose.prod.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'
```

#### Kernel Parameters
```bash
# /etc/sysctl.conf
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
```

## Troubleshooting

### Common Issues

#### Service failures
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml restart backend
```

#### Database Issues
```bash
# Check database connectivity
docker compose exec postgres pg_isready -U postgres

# Check database size
docker compose exec postgres psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('biomarker_db'));"

# Check active connections
docker compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Kill long-running queries
docker compose exec postgres psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '1 hour';"
```

#### Performance Issues
```bash
# Check system resources
htop
iotop
nethogs

# Check Docker resource usage
docker stats

# Check disk I/O
iostat -x 1

# Check network usage
iftop
```

### Diagnostic Commands

#### System diagnostics
```bash
# System information
uname -a
lsb_release -a
docker --version
docker compose version

# Resource usage
free -h
df -h
lscpu
lshw -short

# Network connectivity
ping -c 4 8.8.8.8
nslookup your-domain.com
telnet localhost 80
telnet localhost 443
```

#### Application diagnostics
```bash
curl -v http://localhost:8000/health/ready
curl -v http://localhost:8000/api/status
# Use `docker compose exec` with your service names and the correct DATABASE_URL/REDIS_URL
```

## Disaster Recovery

### Recovery Procedures

#### Complete System Recovery
1. **Prepare New Server**
   - Install operating system
   - Install Docker and Docker Compose
   - Configure network and security

2. **Restore Application**
   - Clone repository
   - Restore configuration files
   - Restore SSL certificates

3. **Restore Data**
   - Restore database from backup
   - Restore file system from backup
   - Verify data integrity

4. **Start Services**
   - Start all services
   - Verify functionality
   - Update DNS records

#### Partial Recovery
1. **Service Recovery**
   - Restart failed services
   - Check service dependencies
   - Verify service health

2. **Data Recovery**
   - Restore specific data
   - Verify data consistency
   - Update application state

### Recovery Testing

#### Regular Testing
- **Monthly**: Test backup restoration
- **Quarterly**: Full disaster recovery test
- **Annually**: Complete system recovery test

#### Testing Procedures
1. **Backup Verification**
   - Test backup integrity
   - Verify backup completeness
   - Test restoration process

2. **Recovery Testing**
   - Simulate disaster scenarios
   - Test recovery procedures
   - Measure recovery time

3. **Documentation Updates**
   - Update recovery procedures
   - Document lessons learned
   - Improve recovery processes

---

## Support and maintenance

For repository contacts and community links, see the **Support** section in [README.md](../README.md) at the repo root.

### Maintenance Schedule
- **Daily**: System health checks
- **Weekly**: Backup verification
- **Monthly**: Security updates
- **Quarterly**: Performance optimization
- **Annually**: Disaster recovery testing

Operational runbooks: [OPERATIONS_AND_RUNBOOKS.md](OPERATIONS_AND_RUNBOOKS.md).
