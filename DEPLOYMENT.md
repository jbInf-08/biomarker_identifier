# Deployment Guide

This guide provides instructions for deploying the Cancer Biomarker Identifier application in various environments. **Authoritative files for this repository** are the root [docker-compose.yml](docker-compose.yml), [docker-compose.prod.yml](docker-compose.prod.yml), [HOW_TO_RUN.md](HOW_TO_RUN.md), and [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md). Prefer the Compose V2 CLI: `docker compose` (not the legacy `docker-compose` v1 binary).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring and Logging](#monitoring-and-logging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+), macOS, or Windows 10+
- **Memory**: Minimum 8GB RAM (16GB recommended for production)
- **Storage**: Minimum 50GB free space
- **CPU**: 4+ cores recommended

### Software Requirements

- **Docker**: 20.10+ and Docker Compose 2.0+
- **Python**: 3.9+
- **Node.js**: 18+
- **PostgreSQL**: 13+
- **Redis**: 6+

### External Services

- **COSMIC API**: For cancer mutation data
- **ClinVar API**: For clinical variant data
- **OncoKB API**: For cancer knowledge base
- **PubMed API**: For literature mining

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier
```

### 2. Environment Variables

Create environment files for different environments:

#### Development and production (examples)

The backend reads settings from Pydantic `Settings` in `backend/app/core/config.py`. For local full-stack runs, start from [production.env.example](production.env.example) (copy to `.env` at the repo root) and [backend/.env.example](backend/.env.example) (copy to `backend/.env` when running the API on the host). See the root [README.md](README.md) configuration table for the full variable list. The snippets below are illustrative only.

**Development (illustrative `.env` fragment)**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/biomarker_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
```

**Production (illustrative `.env` fragment)**

```bash
DATABASE_URL=postgresql://user:password@db-host:5432/biomarker_db
REDIS_URL=redis://redis-host:6379/0
SECRET_KEY=very-secure-secret-key-256-bits
DEBUG=False
# docker-compose.prod.yml also expects BIOMARKER_DOCKER_USERNAME, image tags, and API keys as needed
```

## Development Deployment

### 1. Local Development Setup

```bash
# Start development environment
docker compose up -d

# Install frontend dependencies
cd frontend
npm install

# Install backend dependencies
cd ../backend
pip install -r requirements.txt

# Run database migrations
python -m alembic upgrade head

# Start development servers
# Backend (Terminal 1)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Terminal 2)
cd frontend
npm start
```

### 2. Development with Docker

```bash
# Build and start all services
docker compose up --build

# View logs
docker compose logs -f

# Stop services
docker compose down
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

# The Docker Engine install above includes the Compose V2 plugin (`docker compose version`).
# On some Linux distros: sudo apt install docker-compose-plugin
```

### 2. Production Deployment

`docker-compose.prod.yml` expects pre-built images (for example `your-registry/biomarker-identifier-backend:latest`) and `${BIOMARKER_DOCKER_USERNAME}`. See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) and [docker-compose.prod.yml](docker-compose.prod.yml).

```bash
# Clone repository
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier

# Set environment variables
cp production.env.example .env.prod
# Edit .env.prod with your production values (including BIOMARKER_DOCKER_USERNAME, registry images, SECRET_KEY, DB password)

# Build and deploy
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 3. SSL Certificate Setup

`docker-compose.prod.yml` mounts `./nginx/nginx.prod.conf` and `./nginx/ssl/`. For TLS, place certificates in `nginx/ssl/` or use Certbot, then copy PEM files as in [HOW_TO_RUN.md](HOW_TO_RUN.md) / Nginx setup in [docs/SYSTEM_ADMINISTRATION_GUIDE.md](docs/SYSTEM_ADMINISTRATION_GUIDE.md).

```bash
# Example: install Certbot and obtain certificates
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to the repo nginx directory for compose bind mounts
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./nginx/ssl/

# Restart nginx
docker compose -f docker-compose.prod.yml restart nginx
```

## Docker Deployment

### 1. Build Images

```bash
# Build backend image
cd backend
docker build -t biomarker-identifier-backend:latest .

# Build frontend image
cd ../frontend
docker build -t biomarker-identifier-frontend:latest .
```

### 2. Push to Registry

```bash
# Tag images
docker tag biomarker-identifier-backend:latest your-registry/biomarker-identifier-backend:latest
docker tag biomarker-identifier-frontend:latest your-registry/biomarker-identifier-frontend:latest

# Push images
docker push your-registry/biomarker-identifier-backend:latest
docker push your-registry/biomarker-identifier-frontend:latest
```

### 3. Deploy with Docker Compose

```bash
# Production deployment
docker compose -f docker-compose.prod.yml up -d

# Scale services
docker compose -f docker-compose.prod.yml up -d --scale backend=3 --scale celery-worker=5
```

## Kubernetes Deployment

Example manifests live in [`k8s/`](k8s/). **Adjust namespaces, image names, and resource limits** before applying in your cluster. `k8s/ingress.yaml` references cert-manager annotations (ClusterIssuer). Install [cert-manager](https://cert-manager.io/) in your cluster if you use those TLS resources, or edit the ingress for your own TLS.

### 1. Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. Data stores

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
```

### 3. Application

```bash
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/celery.yaml
```

### 4. Autoscaling and ingress (optional)

```bash
kubectl apply -f k8s/backend-hpa.yaml
kubectl apply -f k8s/ingress.yaml
```

## Cloud Deployment

### AWS Deployment

#### 1. ECS Deployment

The repository does not ship a ready-to-apply `aws/ecs-task-definition.json`; the pattern below is illustrative. Replace with your own task JSON and ECR image URIs.

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name biomarker-identifier

# Create task definition
aws ecs register-task-definition --cli-input-json file://path/to/your/ecs-task-definition.json

# Create service
aws ecs create-service --cluster biomarker-identifier --service-name biomarker-api --task-definition biomarker-identifier:1 --desired-count 2
```

#### 2. EKS Deployment

```bash
# Create EKS cluster
eksctl create cluster --name biomarker-identifier --region us-west-2 --nodegroup-name workers --node-type t3.medium --nodes 3

# Deploy application
kubectl apply -f k8s/
```

### Google Cloud Deployment

#### 1. GKE Deployment

```bash
# Create GKE cluster
gcloud container clusters create biomarker-identifier --zone us-central1-a --num-nodes 3

# Deploy application
kubectl apply -f k8s/
```

### Azure Deployment

#### 1. AKS Deployment

```bash
# Create AKS cluster
az aks create --resource-group myResourceGroup --name biomarker-identifier --node-count 3 --enable-addons monitoring

# Deploy application
kubectl apply -f k8s/
```

## Monitoring and Logging

### 1. Prometheus Setup

```bash
# Deploy Prometheus
docker compose -f docker-compose.prod.yml up -d prometheus

# Access Prometheus UI
open http://localhost:9090
```

### 2. Grafana Setup

```bash
# Deploy Grafana
docker compose -f docker-compose.prod.yml up -d grafana

# Access Grafana UI
open http://localhost:3000
# In docker-compose.prod.yml, admin password is GF_SECURITY_ADMIN_PASSWORD (or GRAFANA_PASSWORD from .env; default "admin" if unset)
```

### 3. Log Management

```bash
# View application logs
docker compose -f docker-compose.prod.yml logs -f backend

# View all logs
docker compose -f docker-compose.prod.yml logs -f

# Log rotation setup
sudo logrotate -f /etc/logrotate.d/docker
```

### 4. Automated verification (CI and pre-release)

- **GitHub Actions**: `.github/workflows/ci.yml` runs backend unit, integration, and E2E tests (with Redis/Postgres services; Celery worker and API server are started where needed), plus frontend `npm run test:coverage` and image checks.
- **Local parity:** from `backend/`, run `python -m pytest tests/` with `SECRET_KEY` and `DEBUG` set. From `frontend/`, run `npm run test:ci`. See `TESTING_GUIDE.md` and `docs/INTEGRATION_TESTING.md` for the full story.
- **Production-style stack smoke**: `docker compose -f docker-compose.prod.yml` (or your environment’s compose file) for metrics and log checks above.

## Security Considerations

### 1. Network Security

- Use HTTPS in production
- Configure firewall rules
- Use VPC for cloud deployments
- Enable DDoS protection

### 2. Application Security

- Use strong passwords
- Enable two-factor authentication
- Regular security updates
- Input validation and sanitization

### 3. Data Security

- Encrypt data at rest
- Encrypt data in transit
- Regular backups
- Access control and auditing

### 4. Container Security

- Use non-root users
- Scan images for vulnerabilities
- Keep base images updated
- Use secrets management

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

```bash
# Check database status
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Test connection (from host, default compose uses DB name biomarker_db)
docker compose exec postgres psql -U postgres -d biomarker_db -c "SELECT 1"
```

#### 2. Redis Connection Issues

```bash
# Check Redis status
docker compose ps redis

# Test Redis connection
docker compose exec backend python -c "import redis; r = redis.Redis(host='redis', port=6379); print(r.ping())"
```

#### 3. Celery Worker Issues

```bash
# Check Celery status
docker compose ps celery-worker

# View Celery logs
docker compose logs celery-worker

# Restart Celery workers
docker compose restart celery-worker
```

#### 4. Frontend Build Issues

```bash
# Check frontend build
docker compose logs frontend

# Rebuild frontend
docker compose build frontend
docker compose up -d frontend
```

### Performance Optimization

#### 1. Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_analysis_runs_user_id ON analysis_runs(user_id);
CREATE INDEX idx_biomarker_results_run_id ON biomarker_results(run_id);
CREATE INDEX idx_user_activities_user_id ON user_activities(user_id);

-- Analyze tables
ANALYZE analysis_runs;
ANALYZE biomarker_results;
ANALYZE user_activities;
```

#### 2. Redis Optimization

```bash
# Configure Redis memory
echo "maxmemory 2gb" >> redis.conf
echo "maxmemory-policy allkeys-lru" >> redis.conf
```

#### 3. Application Optimization

```bash
# Increase worker processes
docker compose -f docker-compose.prod.yml up -d --scale backend=4 --scale celery-worker=6

# Monitor resource usage
docker stats
```

### Backup and Recovery

#### 1. Database Backup

```bash
# Create backup
docker compose exec postgres pg_dump -U postgres biomarker_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker compose exec -T postgres psql -U postgres biomarker_db < backup_20231201_120000.sql
```

#### 2. Application Data Backup

```bash
# Backup application data
docker compose exec backend tar -czf /app/data/backup_$(date +%Y%m%d_%H%M%S).tar.gz /app/data

# Restore application data
docker compose exec backend tar -xzf /app/data/backup_20231201_120000.tar.gz -C /
```

## Support

For deployment support and issues:

- **How to run**: [HOW_TO_RUN.md](HOW_TO_RUN.md) · [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)
- **Issues**: [GitHub Issues](https://github.com/jbInf-08/biomarker_identifier/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jbInf-08/biomarker_identifier/discussions)
- **Email (maintainer)**: As listed in the root [README.md](README.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
