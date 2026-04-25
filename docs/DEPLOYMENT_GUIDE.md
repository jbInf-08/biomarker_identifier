# Cancer Biomarker Identifier - Deployment Guide

**Status (April 2026):** this document contains **generic** deployment patterns. For
this repository, prefer the live files [docker-compose.yml](../docker-compose.yml),
[docker-compose.prod.yml](../docker-compose.prod.yml), [DEPLOYMENT.md](../DEPLOYMENT.md),
[HOW_TO_RUN.md](../HOW_TO_RUN.md), and [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). There is
no `docker-compose.dev.yml` in the repo; use the default compose file for local
full-stack runs.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development Setup](#local-development-setup)
4. [Docker Deployment](#docker-deployment)
5. [Production Deployment](#production-deployment)
6. [Cloud Deployment](#cloud-deployment)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Security Considerations](#security-considerations)

## Overview

This guide provides comprehensive instructions for deploying the Cancer Biomarker Identifier application in various environments, from local development to production cloud deployments.

### Architecture Overview

The application consists of:
- **Frontend**: React.js web application
- **Backend**: FastAPI Python application
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Processing**: Celery
- **Monitoring**: Prometheus + Grafana
- **Containerization**: Docker + Docker Compose

## Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 50 GB free space
- **OS**: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows 10+

#### Recommended Requirements
- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **Storage**: 100+ GB SSD
- **OS**: Linux (Ubuntu 22.04 LTS)

### Software Dependencies

#### Required Software
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Git**: 2.30+
- **Python**: 3.9+ (for local development)
- **Node.js**: 18+ (for local development; matches CI)

#### Optional software
- **Kubernetes** — example manifests under `k8s/` in this repository
- **Helm / Terraform** — not required for the core Docker path

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier
```

### 2. Environment configuration

Copy and edit the root `production.env.example` (or `env.template` as a long reference) and, for API-only work, `backend/.env` from `backend/.env.example`. The backend reads `Settings` from `app.core.config` — see the root `README` “Configuration” table.

### 3. Start the stack (this repository)

**Docker Compose (recommended for parity with CI / demos):**

```bash
docker compose up -d --build
```

- **Frontend (default compose):** http://localhost
- **Backend API:** http://localhost:8000
- **API docs:** http://localhost:8000/docs
- **Postgres (host):** `localhost:5433` → container `5432` (see `docker-compose.yml`)

`docker compose -f docker-compose.prod.yml` adds Nginx, Prometheus, Grafana, etc. Grafana maps **port 3000** on the host in that file; Prometheus is **9090** when the services are included.

### 4. Migrations and admin

Migrations run via the one-shot `migrate` service in `docker-compose.yml` on full `up`, or you can `docker compose run --rm migrate`. Creating an initial admin is environment-specific; see [SYSTEM_ADMINISTRATION_GUIDE.md](SYSTEM_ADMINISTRATION_GUIDE.md) for a Python one-liner with `app.models.user_model.User`.

### 5. Manual (non-Docker) backend + frontend

For hot-reload, see [HOW_TO_RUN.md](../HOW_TO_RUN.md) Path B: Postgres + Redis in Docker, `uvicorn` and `celery -A app.services.celery_service:celery_app` on the host, and `npm start` for the React app.

## Docker Deployment

### 1. Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      target: production
    ports:
      - "80:80"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    depends_on:
      - backend

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: production
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://biomarker_user:${POSTGRES_PASSWORD}@postgres:5432/biomarker_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
      - ./models:/app/models

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=biomarker_db
      - POSTGRES_USER=biomarker_user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  celery:
    build:
      context: .
      dockerfile: backend/Dockerfile
      target: production
    command: celery -A app.services.celery_service:celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://biomarker_user:${POSTGRES_PASSWORD}@postgres:5432/biomarker_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
      - ./models:/app/models

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### 2. Deploy with Docker Compose

```bash
# Set production environment variables
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export GRAFANA_PASSWORD=$(openssl rand -base64 32)

# Start production services
docker compose -f docker-compose.prod.yml up -d

# Check service status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 3. SSL/TLS Configuration

For production deployments, configure SSL/TLS:

```bash
# Generate SSL certificates (using Let's Encrypt)
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Update docker-compose.prod.yml to include nginx with SSL
```

## Production Deployment

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install additional tools
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2. Nginx Configuration

Create `/etc/nginx/sites-available/biomarker-app`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static/ {
        alias /path/to/static/files/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/biomarker-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. SSL Certificate

```bash
# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### 4. Systemd service (example)

Create `/etc/systemd/system/biomarker-app.service`. The Compose v2 **plugin** uses
`docker compose` (space); adjust paths to match the machine where the repo lives.

```ini
[Unit]
Description=Cancer Biomarker Identifier
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/biomarker_identifier
ExecStart=/bin/sh -c 'docker compose -f docker-compose.prod.yml up -d'
ExecStop=/bin/sh -c 'docker compose -f docker-compose.prod.yml down'
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

If you only have a legacy `docker-compose` (v1) single binary, replace the `ExecStart` /
`ExecStop` lines with that binary and the same flags.

Enable and start the service:

```bash
sudo systemctl enable biomarker-app
sudo systemctl start biomarker-app
sudo systemctl status biomarker-app
```

## Cloud Deployment

### AWS Deployment

#### 1. Infrastructure Setup

Create `terraform/main.tf`:

```hcl
provider "aws" {
  region = "us-west-2"
}

# VPC and Networking
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "biomarker-app-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-west-2a"
  map_public_ip_on_launch = true

  tags = {
    Name = "biomarker-app-public-subnet"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier     = "biomarker-postgres"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.micro"
  allocated_storage = 20

  db_name  = "biomarker_db"
  username = "biomarker_user"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  skip_final_snapshot = true
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "main" {
  name       = "biomarker-redis-subnet"
  subnet_ids = [aws_subnet.private.id]
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "biomarker-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "biomarker-app"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "biomarker-app-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public.id]

  enable_deletion_protection = false
}
```

#### 2. ECS Task Definition

Create `aws/ecs-task-definition.json`:

```json
{
  "family": "biomarker-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "your-account.dkr.ecr.us-west-2.amazonaws.com/biomarker-frontend:latest",
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/biomarker-app",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    },
    {
      "name": "backend",
      "image": "your-account.dkr.ecr.us-west-2.amazonaws.com/biomarker-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://biomarker_user:PASSWORD@biomarker-postgres.region.rds.amazonaws.com:5432/biomarker_db"
        },
        {
          "name": "REDIS_URL",
          "value": "redis://biomarker-redis.region.cache.amazonaws.com:6379/0"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/biomarker-app",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Google Cloud Platform Deployment

#### 1. Google Kubernetes Engine

Create `gcp/k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: biomarker-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: biomarker-app
  template:
    metadata:
      labels:
        app: biomarker-app
    spec:
      containers:
      - name: frontend
        image: gcr.io/your-project/biomarker-frontend:latest
        ports:
        - containerPort: 80
        env:
        - name: REACT_APP_API_URL
          value: "https://api.your-domain.com"
      - name: backend
        image: gcr.io/your-project/biomarker-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: biomarker-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: biomarker-secrets
              key: redis-url
---
apiVersion: v1
kind: Service
metadata:
  name: biomarker-app-service
spec:
  selector:
    app: biomarker-app
  ports:
  - name: frontend
    port: 80
    targetPort: 80
  - name: backend
    port: 8000
    targetPort: 8000
  type: LoadBalancer
```

#### 2. Deploy to GKE

```bash
# Create cluster
gcloud container clusters create biomarker-cluster \
  --zone=us-central1-a \
  --num-nodes=3 \
  --machine-type=e2-medium

# Deploy application
kubectl apply -f gcp/k8s-deployment.yaml

# Get external IP
kubectl get services
```

## Monitoring and Maintenance

### 1. Health Checks

Create health check endpoints:

```python
# backend/app/api/routes/health.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    checks = {
        "database": await check_database_connection(db),
        "redis": await check_redis_connection(),
        "celery": await check_celery_workers(),
        "storage": await check_storage_space()
    }
    
    overall_status = "healthy" if all(checks.values()) else "unhealthy"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }
```

### 2. Logging Configuration

Configure structured logging:

```python
# backend/app/utils/logging_config.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
            
        return json.dumps(log_entry)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log')
    ]
)

logger = logging.getLogger(__name__)
logger.handlers[0].setFormatter(JSONFormatter())
```

### 3. Backup Strategy

Create backup scripts:

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
docker compose exec -T postgres pg_dump -U biomarker_user biomarker_db > \
  $BACKUP_DIR/database_$DATE.sql

# Application data backup
tar -czf $BACKUP_DIR/data_$DATE.tar.gz ./data ./reports ./models

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Schedule backups with cron:

```bash
# Add to crontab
0 2 * * * /path/to/scripts/backup.sh
```

### 4. Monitoring Alerts

Configure Prometheus alerts:

```yaml
# monitoring/alerts.yml
groups:
- name: biomarker-app
  rules:
  - alert: HighCPUUsage
    expr: cpu_usage_percent > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage detected"
      description: "CPU usage is above 80% for 5 minutes"

  - alert: DatabaseConnectionFailed
    expr: database_connections_failed > 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database connection failed"
      description: "Failed to connect to database"

  - alert: DiskSpaceLow
    expr: disk_usage_percent > 90
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Disk space low"
      description: "Disk usage is above 90%"
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

```bash
# Check database status
docker compose exec postgres pg_isready -U biomarker_user

# Check database logs
docker compose logs postgres

# Reset database
docker compose down
docker volume rm biomarker_postgres_data
docker compose up -d
```

#### 2. Redis Connection Issues

```bash
# Check Redis status
docker compose exec redis redis-cli ping

# Check Redis logs
docker compose logs redis

# Clear Redis cache
docker compose exec redis redis-cli FLUSHALL
```

#### 3. Celery Worker Issues

```bash
# Check Celery status (service name may be celery-worker in this repo)
docker compose exec celery-worker celery -A app.services.celery_service:celery_app inspect active

# Restart workers
docker compose restart celery-worker

# Worker logs
docker compose logs celery-worker
```

#### 4. Frontend Build Issues

```bash
# Clear npm cache
docker compose exec frontend npm cache clean --force

# Rebuild frontend
docker compose build --no-cache frontend

# Check frontend logs
docker compose logs frontend
```

### Performance Optimization

#### 1. Database Optimization

```sql
-- Create indexes for better performance
CREATE INDEX idx_biomarker_results_run_id ON biomarker_results(run_id);
CREATE INDEX idx_biomarker_results_gene_symbol ON biomarker_results(gene_symbol);
CREATE INDEX idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX idx_analysis_runs_created_at ON analysis_runs(created_at);

-- Analyze tables for query optimization
ANALYZE biomarker_results;
ANALYZE analysis_runs;
```

#### 2. Redis Optimization

```bash
# Configure Redis for better performance
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

#### 3. Application Optimization

```python
# backend/app/core/config.py
class Settings:
    # Database connection pooling
    DATABASE_POOL_SIZE = 20
    DATABASE_MAX_OVERFLOW = 30
    
    # Redis connection pooling
    REDIS_POOL_SIZE = 20
    
    # Celery configuration
    CELERY_WORKER_CONCURRENCY = 4
    CELERY_TASK_TIME_LIMIT = 3600
    CELERY_TASK_SOFT_TIME_LIMIT = 3000
```

## Security Considerations

### 1. Environment Variables

```bash
# Use strong passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)
SECRET_KEY=$(openssl rand -base64 64)
JWT_SECRET=$(openssl rand -base64 64)

# Store in secure location
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env.prod
echo "SECRET_KEY=$SECRET_KEY" >> .env.prod
echo "JWT_SECRET=$JWT_SECRET" >> .env.prod
```

### 2. Network Security

```yaml
# docker-compose.prod.yml
services:
  backend:
    networks:
      - app-network
    # Don't expose ports directly

  postgres:
    networks:
      - app-network
    # Internal access only

networks:
  app-network:
    driver: bridge
    internal: true
```

### 3. File Permissions

```bash
# Set proper file permissions
chmod 600 .env.prod
chmod 700 ./data
chmod 700 ./reports
chmod 700 ./models

# Create non-root user for containers
# Dockerfile
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

### 4. SSL/TLS Configuration

```nginx
# nginx.conf
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
```

---

## Support and Maintenance

### Regular Maintenance Tasks

1. **Weekly**:
   - Check system logs for errors
   - Monitor disk space usage
   - Review security updates

2. **Monthly**:
   - Update dependencies
   - Review and rotate logs
   - Test backup and restore procedures

3. **Quarterly**:
   - Security audit
   - Performance review
   - Disaster recovery testing

### Contact information

Use the maintainers and community links in the root [README.md](../README.md).

---

*Last updated: April 2026*
