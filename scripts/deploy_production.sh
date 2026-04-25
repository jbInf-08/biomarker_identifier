#!/bin/bash

# Production Deployment Script for Biomarker Identifier
# This script handles the complete production deployment process

set -e

# Configuration
PROJECT_NAME="biomarker-identifier"
DOCKER_USERNAME="${DOCKER_USERNAME:-your-docker-username}"
ENVIRONMENT="${ENVIRONMENT:-production}"
BACKUP_DIR="/opt/backups/biomarker-identifier"
LOG_DIR="/var/log/biomarker-identifier"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    # Check if required environment variables are set
    if [ -z "$POSTGRES_PASSWORD" ]; then
        error "POSTGRES_PASSWORD environment variable is not set"
    fi
    
    if [ -z "$SECRET_KEY" ]; then
        error "SECRET_KEY environment variable is not set"
    fi
    
    log "Prerequisites check passed"
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    sudo mkdir -p "$BACKUP_DIR"
    sudo mkdir -p "$LOG_DIR"
    sudo mkdir -p "/opt/biomarker-identifier/nginx/ssl"
    sudo mkdir -p "/opt/biomarker-identifier/monitoring"
    
    # Set permissions
    sudo chown -R $USER:$USER "$BACKUP_DIR"
    sudo chown -R $USER:$USER "$LOG_DIR"
    sudo chown -R $USER:$USER "/opt/biomarker-identifier"
    
    log "Directories created successfully"
}

# Backup existing deployment
backup_existing() {
    if [ -f "docker-compose.prod.yml" ]; then
        log "Creating backup of existing deployment..."
        
        BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
        
        # Backup database
        if docker-compose -f docker-compose.prod.yml ps postgres | grep -q "Up"; then
            log "Backing up database..."
            docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres biomarker_db > "$BACKUP_DIR/$BACKUP_NAME/database.sql"
        fi
        
        # Backup application data
        if docker-compose -f docker-compose.prod.yml ps backend | grep -q "Up"; then
            log "Backing up application data..."
            docker-compose -f docker-compose.prod.yml exec -T backend tar -czf - /app/data > "$BACKUP_DIR/$BACKUP_NAME/application_data.tar.gz"
        fi
        
        # Backup configuration files
        cp docker-compose.prod.yml "$BACKUP_DIR/$BACKUP_NAME/"
        cp -r monitoring/ "$BACKUP_DIR/$BACKUP_NAME/"
        cp -r k8s/ "$BACKUP_DIR/$BACKUP_NAME/"
        
        log "Backup completed: $BACKUP_DIR/$BACKUP_NAME"
    fi
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    # Build backend image
    log "Building backend image..."
    docker build -t "$DOCKER_USERNAME/biomarker-identifier-backend:latest" ./backend/
    
    # Build frontend image
    log "Building frontend image..."
    docker build -t "$DOCKER_USERNAME/biomarker-identifier-frontend:latest" ./frontend/
    
    log "Docker images built successfully"
}

# Deploy services
deploy_services() {
    log "Deploying services..."
    
    # Stop existing services
    if [ -f "docker-compose.prod.yml" ]; then
        log "Stopping existing services..."
        docker-compose -f docker-compose.prod.yml down
    fi
    
    # Start services
    log "Starting services..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_service_health
}

# Check service health
check_service_health() {
    log "Checking service health..."
    
    # Check backend
    if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
        error "Backend service is not healthy"
    fi
    
    # Check frontend
    if ! curl -f http://localhost:80 > /dev/null 2>&1; then
        error "Frontend service is not healthy"
    fi
    
    # Check database
    if ! docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        error "Database is not healthy"
    fi
    
    # Check Redis
    if ! docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
        error "Redis is not healthy"
    fi
    
    log "All services are healthy"
}

# Setup SSL certificates
setup_ssl() {
    if [ "$ENVIRONMENT" = "production" ]; then
        log "Setting up SSL certificates..."
        
        # Check if certificates exist
        if [ ! -f "/opt/biomarker-identifier/nginx/ssl/fullchain.pem" ]; then
            warning "SSL certificates not found. Please install certificates manually."
            warning "Place certificates in /opt/biomarker-identifier/nginx/ssl/"
        else
            log "SSL certificates found"
        fi
    fi
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Copy monitoring configuration
    cp -r monitoring/* /opt/biomarker-identifier/monitoring/
    
    # Start monitoring services
    docker-compose -f docker-compose.prod.yml up -d prometheus grafana
    
    log "Monitoring setup completed"
    log "Prometheus: http://localhost:9090"
    log "Grafana: http://localhost:3000 (admin/admin)"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."
    
    # Wait for database to be ready
    sleep 10
    
    # Run migrations
    docker-compose -f docker-compose.prod.yml exec -T backend python -m alembic upgrade head
    
    log "Database migrations completed"
}

# Setup log rotation
setup_log_rotation() {
    log "Setting up log rotation..."
    
    cat > /tmp/biomarker-logrotate << EOF
/var/log/biomarker-identifier/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        docker-compose -f /opt/biomarker-identifier/docker-compose.prod.yml restart backend
    endscript
}
EOF
    
    sudo mv /tmp/biomarker-logrotate /etc/logrotate.d/biomarker-identifier
    log "Log rotation configured"
}

# Setup systemd service
setup_systemd_service() {
    log "Setting up systemd service..."
    
    cat > /tmp/biomarker-identifier.service << EOF
[Unit]
Description=Biomarker Identifier Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/biomarker-identifier
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    sudo mv /tmp/biomarker-identifier.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable biomarker-identifier.service
    
    log "Systemd service configured"
}

# Performance optimization
optimize_performance() {
    log "Optimizing performance..."
    
    # Increase file limits
    echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
    echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
    
    # Optimize Docker daemon
    sudo mkdir -p /etc/docker
    cat > /tmp/daemon.json << EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 65536,
            "Soft": 65536
        }
    }
}
EOF
    
    sudo mv /tmp/daemon.json /etc/docker/daemon.json
    sudo systemctl restart docker
    
    log "Performance optimization completed"
}

# Security hardening
security_hardening() {
    log "Applying security hardening..."
    
    # Create non-root user for application
    sudo useradd -r -s /bin/false biomarker-app || true
    
    # Set up firewall rules
    sudo ufw allow 22/tcp
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable
    
    # Disable unnecessary services
    sudo systemctl disable apache2 || true
    sudo systemctl disable nginx || true
    
    log "Security hardening completed"
}

# Main deployment function
main() {
    log "Starting production deployment of Biomarker Identifier..."
    
    check_prerequisites
    create_directories
    backup_existing
    build_images
    deploy_services
    setup_ssl
    setup_monitoring
    run_migrations
    setup_log_rotation
    setup_systemd_service
    optimize_performance
    security_hardening
    
    log "Production deployment completed successfully!"
    log "Application is available at: http://localhost"
    log "Monitoring: http://localhost:3000 (Grafana)"
    log "Metrics: http://localhost:9090 (Prometheus)"
    log "Celery Monitor: http://localhost:5555 (Flower)"
    
    # Display service status
    log "Service Status:"
    docker-compose -f docker-compose.prod.yml ps
}

# Run main function
main "$@"
