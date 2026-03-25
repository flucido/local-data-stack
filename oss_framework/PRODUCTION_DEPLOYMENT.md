# Production Deployment Guide - Local Data Stack

## Overview

This document provides step-by-step instructions for deploying the local-data-stack analytics platform to production using Docker Compose. The architecture is **100% local** with no cloud dependencies, designed for on-premises deployment with high availability through traditional infrastructure approaches.

---

## Architecture

### Local-First Production Stack

```
┌─────────────────────────────────────────────────────────────┐
│                Production Deployment (On-Premises)          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐    ┌─────────────────────────────┐  │
│  │  Load Balancer   │───▶│  Application Servers (2+)   │  │
│  │  (HAProxy/nginx) │    │  ├─ Docker Compose Stack   │  │
│  └──────────────────┘    │  ├─ Rill (port 9009)        │  │
│                           │  └─ JupyterLab (port 8888)  │  │
│                           └─────────────────────────────┘  │
│                                     │                       │
│                                     ▼                       │
│                           ┌─────────────────────────────┐  │
│                           │  Shared Storage (NFS/NAS)   │  │
│                           │  ├─ DuckDB file (.duckdb)   │  │
│                           │  ├─ Stage 1 Parquet files   │  │
│                           │  ├─ Stage 2/3 data          │  │
│                           │  └─ Backups                 │  │
│                           └─────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Components**:
- **Docker Compose**: Container orchestration (Rill + JupyterLab)
- **DuckDB**: Analytical database (file-based, no server)
- **Shared Storage**: NFS/NAS for DuckDB file and data directories
- **Load Balancer**: HAProxy or nginx for high availability
- **Backup Strategy**: Automated DuckDB file backups with encryption

---

## Pre-Deployment Checklist

### Infrastructure Prerequisites

- [ ] Production server(s) provisioned (2+ for HA)
  - Minimum per server: 8 CPU cores, 32GB RAM, 500GB SSD
  - OS: Ubuntu 22.04 LTS or RHEL 9
- [ ] Docker Engine installed (v24.0+) on all servers
- [ ] Docker Compose installed (v2.20+) on all servers
- [ ] Shared storage configured (NFS/NAS) with 1TB+ capacity
- [ ] Load balancer configured (HAProxy, nginx, or cloud LB)
- [ ] SSL/TLS certificates generated for HTTPS
- [ ] Firewall rules configured (ports 9009, 8888, 443)
- [ ] Backup destination configured (encrypted storage)

### Code & Data Prerequisites

- [ ] Git repository cloned to `/opt/local-data-stack/`
- [ ] `.env` file configured with production values
- [ ] dbt project tested locally (all models passing)
- [ ] Initial data ingestion completed and validated
- [ ] DuckDB file exists and is healthy (`PRAGMA integrity_check`)
- [ ] Python dependencies installed (`pip install -e .`)

### Organizational Prerequisites

- [ ] Change control process approved
- [ ] Incident response team briefed
- [ ] Rollback procedure documented and tested
- [ ] Monitoring and alerting configured
- [ ] Support team trained on operational procedures (see `OPERATIONAL_RUNBOOKS.md`)
- [ ] Backup/recovery tested

---

## Step 1: Infrastructure Setup

### 1.1 Install Docker on Production Servers

```bash
#!/bin/bash
# Install Docker Engine and Docker Compose on Ubuntu 22.04

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Start Docker service
sudo systemctl enable docker
sudo systemctl start docker

echo "✅ Docker installed successfully"
```

---

### 1.2 Configure Shared Storage (NFS)

**On NFS Server:**

```bash
#!/bin/bash
# Setup NFS server for shared DuckDB storage

# Install NFS server
sudo apt-get install nfs-kernel-server -y

# Create shared directory
sudo mkdir -p /srv/nfs/local-data-stack
sudo chown nobody:nogroup /srv/nfs/local-data-stack
sudo chmod 777 /srv/nfs/local-data-stack

# Configure NFS exports
echo "/srv/nfs/local-data-stack 10.0.0.0/24(rw,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports

# Restart NFS server
sudo exportfs -a
sudo systemctl restart nfs-kernel-server

echo "✅ NFS server configured"
```

**On Application Servers:**

```bash
#!/bin/bash
# Mount NFS share on application servers

# Install NFS client
sudo apt-get install nfs-common -y

# Create mount point
sudo mkdir -p /opt/local-data-stack/shared-data

# Mount NFS share
sudo mount -t nfs <NFS_SERVER_IP>:/srv/nfs/local-data-stack /opt/local-data-stack/shared-data

# Add to /etc/fstab for persistence
echo "<NFS_SERVER_IP>:/srv/nfs/local-data-stack /opt/local-data-stack/shared-data nfs defaults 0 0" | sudo tee -a /etc/fstab

# Verify mount
df -h | grep local-data-stack

echo "✅ NFS client configured"
```

---

### 1.3 SSL/TLS Certificate Setup

```bash
#!/bin/bash
# Generate SSL certificate (Let's Encrypt or self-signed)

# Option 1: Let's Encrypt (recommended for production)
sudo apt-get install certbot -y
sudo certbot certonly --standalone -d analytics.yourdomain.com

# Option 2: Self-signed certificate (for testing)
sudo mkdir -p /etc/ssl/local-data-stack
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/local-data-stack/privkey.pem \
  -out /etc/ssl/local-data-stack/fullchain.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=analytics.yourdomain.com"

# Set permissions
sudo chmod 600 /etc/ssl/local-data-stack/privkey.pem
sudo chmod 644 /etc/ssl/local-data-stack/fullchain.pem

echo "✅ SSL certificate configured"
```

---

## Step 2: Application Deployment

### 2.1 Clone Repository and Configure Environment

```bash
#!/bin/bash
# Deploy application to production server

# Clone repository
sudo git clone https://github.com/yourusername/local-data-stack.git /opt/local-data-stack
cd /opt/local-data-stack

# Create production environment file
cat > .env << EOF
# Core paths (using shared storage)
DUCKDB_DATABASE_PATH=/opt/local-data-stack/shared-data/oea.duckdb
STAGE1_PATH=/opt/local-data-stack/shared-data/stage1
STAGE2_PATH=/opt/local-data-stack/shared-data/stage2
STAGE3_PATH=/opt/local-data-stack/shared-data/stage3

# Aeries API credentials
AERIES_API_URL=https://api.aeries.com/v5
AERIES_API_KEY=<your_production_api_key>
AERIES_DISTRICT_CODE=<your_district_code>

# Privacy & Security
PRIVACY_SALT=<generate_with_openssl_rand_base64_32>

# Rill configuration
RILL_PORT=9009
RILL_RUNTIME_LOG_LEVEL=info

# Backup configuration
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=30
BACKUP_ENCRYPTION_KEY=<generate_with_openssl_rand_base64_32>
EOF

# Set permissions
sudo chmod 600 .env
sudo chown $USER:docker .env

# Install Python dependencies
pip install -e .

echo "✅ Application configured"
```

---

### 2.2 Create Production Docker Compose Configuration

```bash
#!/bin/bash
# Create production docker-compose.yml with resource limits and health checks

cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  rill:
    image: rilldata/rill:latest
    container_name: local-data-stack-rill-prod
    ports:
      - "9009:9009"
    volumes:
      - ./:/app
      - /opt/local-data-stack/shared-data:/data
    environment:
      - RILL_RUNTIME_LOG_LEVEL=info
      - DUCKDB_DATABASE_PATH=/data/oea.duckdb
    command: rill start --project /app
    restart: always
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9009/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - local-data-stack
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  jupyter:
    image: jupyter/scipy-notebook:latest
    container_name: local-data-stack-jupyter-prod
    ports:
      - "8888:8888"
    volumes:
      - ./:/home/jovyan/work
      - /opt/local-data-stack/shared-data:/home/jovyan/data
    environment:
      - JUPYTER_ENABLE_LAB=yes
      - DUCKDB_DATABASE_PATH=/home/jovyan/data/oea.duckdb
      - STAGE1_PATH=/home/jovyan/data/stage1
      - STAGE2_PATH=/home/jovyan/data/stage2
      - STAGE3_PATH=/home/jovyan/data/stage3
    command: start-notebook.sh --NotebookApp.token='<generate_secure_token>'
    restart: always
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 16G
        reservations:
          cpus: '2'
          memory: 8G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/api"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - local-data-stack
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

networks:
  local-data-stack:
    driver: bridge
EOF

echo "✅ Production Docker Compose configuration created"
```

---

### 2.3 Deploy Services

```bash
#!/bin/bash
# Deploy production stack

cd /opt/local-data-stack

# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Verify deployment
docker-compose -f docker-compose.prod.yml ps

# Check health status
curl -f http://localhost:9009/health && echo "✅ Rill is healthy" || echo "❌ Rill failed health check"
curl -f http://localhost:8888/api && echo "✅ Jupyter is healthy" || echo "❌ Jupyter failed health check"

echo "✅ Services deployed"
```

---

## Step 3: Load Balancer Configuration

### 3.1 HAProxy Configuration (Recommended)

```bash
#!/bin/bash
# Install and configure HAProxy for high availability

# Install HAProxy
sudo apt-get install haproxy -y

# Backup default config
sudo cp /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.bak

# Create production HAProxy configuration
sudo tee /etc/haproxy/haproxy.cfg > /dev/null << 'EOF'
global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

    # SSL configuration
    ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets

defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    timeout connect 5000
    timeout client  50000
    timeout server  50000
    errorfile 400 /etc/haproxy/errors/400.http
    errorfile 403 /etc/haproxy/errors/403.http
    errorfile 408 /etc/haproxy/errors/408.http
    errorfile 500 /etc/haproxy/errors/500.http
    errorfile 502 /etc/haproxy/errors/502.http
    errorfile 503 /etc/haproxy/errors/503.http
    errorfile 504 /etc/haproxy/errors/504.http

# Stats page
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE

# HTTPS frontend
frontend https_front
    bind *:443 ssl crt /etc/ssl/local-data-stack/fullchain.pem
    mode http
    option forwardfor
    
    # Redirect to Rill by default
    default_backend rill_backend

# Rill backend (multiple servers for HA)
backend rill_backend
    mode http
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200
    
    server rill1 10.0.0.10:9009 check inter 5s fall 3 rise 2
    server rill2 10.0.0.11:9009 check inter 5s fall 3 rise 2 backup

# HTTP to HTTPS redirect
frontend http_front
    bind *:80
    mode http
    redirect scheme https code 301 if !{ ssl_fc }
EOF

# Restart HAProxy
sudo systemctl restart haproxy
sudo systemctl enable haproxy

# Verify HAProxy is running
sudo systemctl status haproxy

echo "✅ HAProxy configured"
echo "Access stats at: http://<server-ip>:8404/stats"
```

---

### 3.2 Nginx Configuration (Alternative)

```bash
#!/bin/bash
# Install and configure Nginx as reverse proxy

# Install Nginx
sudo apt-get install nginx -y

# Create Rill site configuration
sudo tee /etc/nginx/sites-available/local-data-stack > /dev/null << 'EOF'
upstream rill_servers {
    least_conn;
    server 10.0.0.10:9009 max_fails=3 fail_timeout=30s;
    server 10.0.0.11:9009 max_fails=3 fail_timeout=30s backup;
}

server {
    listen 80;
    server_name analytics.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name analytics.yourdomain.com;

    ssl_certificate /etc/ssl/local-data-stack/fullchain.pem;
    ssl_certificate_key /etc/ssl/local-data-stack/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://rill_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for Rill live updates)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://rill_servers/health;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/local-data-stack /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx

echo "✅ Nginx configured"
```

---

## Step 4: Backup & Recovery Setup

### 4.1 Automated Backup Script

```bash
#!/bin/bash
# Create automated backup script for DuckDB

sudo tee /opt/local-data-stack/scripts/backup-duckdb.sh > /dev/null << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/opt/local-data-stack/shared-data/backups"
DUCKDB_FILE="/opt/local-data-stack/shared-data/oea.duckdb"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/oea_backup_${TIMESTAMP}.duckdb"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY}"
RETENTION_DAYS=30

echo "📦 Starting DuckDB backup: $(date)"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Step 1: Run CHECKPOINT to ensure data is written to disk
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml exec -T jupyter python3 -c "
import duckdb
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
conn.execute('CHECKPOINT')
print('✅ CHECKPOINT completed')
conn.close()
"

# Step 2: Copy DuckDB file
echo "Copying DuckDB file..."
cp "$DUCKDB_FILE" "$BACKUP_FILE"

# Step 3: Encrypt backup (if encryption key provided)
if [ -n "$ENCRYPTION_KEY" ]; then
    echo "Encrypting backup..."
    openssl enc -aes-256-cbc -salt -in "$BACKUP_FILE" \
        -out "${BACKUP_FILE}.enc" \
        -k "$ENCRYPTION_KEY"
    rm "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.enc"
fi

# Step 4: Verify backup integrity
echo "Verifying backup..."
BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
if [ "$BACKUP_SIZE" -gt 1000000 ]; then
    echo "✅ Backup created: $BACKUP_FILE ($(numfmt --to=iec-i --suffix=B $BACKUP_SIZE))"
else
    echo "❌ Backup failed: File too small"
    exit 1
fi

# Step 5: Cleanup old backups (keep last 30 days)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "oea_backup_*.duckdb*" -mtime +$RETENTION_DAYS -delete

echo "✅ Backup complete: $(date)"
EOF

# Make executable
sudo chmod +x /opt/local-data-stack/scripts/backup-duckdb.sh

echo "✅ Backup script created"
```

---

### 4.2 Schedule Backup with Cron

```bash
#!/bin/bash
# Schedule daily backups at 2 AM

# Add to root crontab
(sudo crontab -l 2>/dev/null; echo "0 2 * * * /opt/local-data-stack/scripts/backup-duckdb.sh >> /var/log/duckdb-backup.log 2>&1") | sudo crontab -

# Verify crontab
sudo crontab -l

echo "✅ Backup scheduled (daily at 2 AM)"
```

---

### 4.3 Restore from Backup

```bash
#!/bin/bash
# Restore DuckDB from backup

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    echo "Available backups:"
    ls -lht /opt/local-data-stack/shared-data/backups/
    exit 1
fi

echo "🔄 Starting database restore from: $BACKUP_FILE"

# Stop services
echo "Stopping services..."
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml down

# Backup current database
echo "Creating safety backup..."
cp /opt/local-data-stack/shared-data/oea.duckdb \
   /opt/local-data-stack/shared-data/oea.duckdb.before_restore.$(date +%Y%m%d_%H%M%S)

# Decrypt if encrypted
if [[ "$BACKUP_FILE" == *.enc ]]; then
    echo "Decrypting backup..."
    openssl enc -aes-256-cbc -d -in "$BACKUP_FILE" \
        -out "${BACKUP_FILE%.enc}" \
        -k "${BACKUP_ENCRYPTION_KEY}"
    BACKUP_FILE="${BACKUP_FILE%.enc}"
fi

# Restore database
echo "Restoring database..."
cp "$BACKUP_FILE" /opt/local-data-stack/shared-data/oea.duckdb

# Restart services
echo "Restarting services..."
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml up -d

# Verify
echo "Verifying restoration..."
sleep 10
curl -f http://localhost:9009/health && echo "✅ Rill is healthy" || echo "❌ Rill failed"

echo "✅ Restore complete"
```

---

## Step 5: Monitoring & Alerting

### 5.1 Install Prometheus + Grafana (Optional)

```bash
#!/bin/bash
# Add monitoring stack to Docker Compose

cat >> docker-compose.prod.yml << 'EOF'

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: always
    networks:
      - local-data-stack

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=<generate_secure_password>
    restart: always
    networks:
      - local-data-stack

volumes:
  prometheus-data:
  grafana-data:
EOF

# Create Prometheus config
mkdir -p monitoring
cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'docker'
    static_configs:
      - targets: ['host.docker.internal:9323']

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
EOF

echo "✅ Monitoring configured"
```

---

### 5.2 Health Check Monitoring

```bash
#!/bin/bash
# Create health check script for monitoring

sudo tee /opt/local-data-stack/scripts/health-check.sh > /dev/null << 'EOF'
#!/bin/bash

RILL_URL="http://localhost:9009/health"
ALERT_EMAIL="ops@yourdomain.com"

check_service() {
    if curl -f -s "$1" > /dev/null; then
        echo "✅ $2 is healthy"
        return 0
    else
        echo "❌ $2 is down"
        echo "$2 health check failed at $(date)" | mail -s "ALERT: $2 Down" "$ALERT_EMAIL"
        return 1
    fi
}

check_service "$RILL_URL" "Rill"

# Check DuckDB file
if [ -f "/opt/local-data-stack/shared-data/oea.duckdb" ]; then
    echo "✅ DuckDB file exists"
else
    echo "❌ DuckDB file missing"
    echo "DuckDB file missing at $(date)" | mail -s "ALERT: DuckDB Missing" "$ALERT_EMAIL"
fi
EOF

sudo chmod +x /opt/local-data-stack/scripts/health-check.sh

# Schedule health checks every 5 minutes
(sudo crontab -l 2>/dev/null; echo "*/5 * * * * /opt/local-data-stack/scripts/health-check.sh >> /var/log/health-check.log 2>&1") | sudo crontab -

echo "✅ Health monitoring configured"
```

---

## Step 6: Verification & Testing

### 6.1 Deployment Verification Checklist

```bash
#!/bin/bash
# Comprehensive deployment verification script

echo "=== Production Deployment Verification ==="

# 1. Check Docker services
echo "1️⃣ Checking Docker services..."
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml ps

# 2. Check health endpoints
echo "2️⃣ Checking health endpoints..."
curl -f http://localhost:9009/health && echo "✅ Rill healthy" || echo "❌ Rill failed"

# 3. Check DuckDB file
echo "3️⃣ Checking DuckDB file..."
ls -lh /opt/local-data-stack/shared-data/oea.duckdb

# 4. Check data freshness
echo "4️⃣ Checking data freshness..."
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml exec -T jupyter python3 -c "
import duckdb
from datetime import datetime
conn = duckdb.connect('/home/jovyan/data/oea.duckdb')
max_date = conn.execute('SELECT MAX(date) FROM mart_core.fact_attendance').fetchone()[0]
hours_old = (datetime.now() - max_date).total_seconds() / 3600 if max_date else 999
print(f'Data is {hours_old:.1f} hours old')
conn.close()
"

# 5. Check disk space
echo "5️⃣ Checking disk space..."
df -h /opt/local-data-stack/shared-data

# 6. Check backups
echo "6️⃣ Checking backups..."
ls -lht /opt/local-data-stack/shared-data/backups/ | head -5

# 7. Test load balancer (if configured)
echo "7️⃣ Testing load balancer..."
curl -f -k https://analytics.yourdomain.com/ && echo "✅ Load balancer working" || echo "⚠️ Load balancer not configured"

echo "=== Verification Complete ==="
```

---

## Step 7: Rollback Procedure

### 7.1 Emergency Rollback Script

```bash
#!/bin/bash
# Rollback to previous version

echo "🔄 Starting rollback procedure..."

# Stop current services
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml down

# Restore previous version from git
cd /opt/local-data-stack
git stash
git checkout <previous-stable-tag>  # e.g., v1.2.0

# Restore previous DuckDB backup
LATEST_BACKUP=$(ls -t /opt/local-data-stack/shared-data/backups/oea_backup_*.duckdb | head -1)
cp "$LATEST_BACKUP" /opt/local-data-stack/shared-data/oea.duckdb

# Start services
docker-compose -f /opt/local-data-stack/docker-compose.prod.yml up -d

echo "✅ Rollback complete"
```

---

## Security Hardening

### 8.1 Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Configure firewall rules (allow only ports 443, 22)
- [ ] Enable Docker content trust: `export DOCKER_CONTENT_TRUST=1`
- [ ] Encrypt backups with strong encryption key
- [ ] Enable audit logging for Docker
- [ ] Implement network segmentation
- [ ] Configure fail2ban for SSH protection
- [ ] Enable automatic security updates
- [ ] Implement least-privilege access controls

See `SECURITY.md` for detailed security guidance.

---

## Scaling Considerations

### 9.1 Vertical Scaling (Single Server)

- Increase Docker container memory limits in `docker-compose.prod.yml`
- Upgrade server CPU/RAM (8 cores → 16 cores, 32GB → 64GB)
- Use faster storage (SSD → NVMe)

### 9.2 Horizontal Scaling (Multiple Servers)

- Deploy identical stacks on multiple servers
- Use HAProxy/nginx for load balancing across servers
- Share DuckDB file via NFS (read replicas)
- **Limitation**: DuckDB is file-based, write operations must go to primary server
- Consider read-only replicas for dashboards (copy DuckDB file periodically)

---

## Troubleshooting

### Common Issues

**Issue**: Rill container fails to start  
**Solution**: Check DuckDB file permissions: `sudo chown -R 1000:1000 /opt/local-data-stack/shared-data/`

**Issue**: NFS mount fails  
**Solution**: Check NFS server is running: `sudo systemctl status nfs-kernel-server`

**Issue**: Health checks failing  
**Solution**: Check container logs: `docker-compose -f /opt/local-data-stack/docker-compose.prod.yml logs`

**Issue**: Out of disk space  
**Solution**: Run cleanup: `docker system prune -a && find /opt/local-data-stack/shared-data/backups -mtime +30 -delete`

---

## Support & Maintenance

### Regular Maintenance Tasks

- **Daily**: Check health monitoring logs
- **Weekly**: Verify backups are running successfully
- **Monthly**: Review disk usage, update Docker images, run security updates
- **Quarterly**: Review performance metrics, capacity planning

### Additional Documentation

- **Operational Procedures**: `OPERATIONAL_RUNBOOKS.md`
- **Security Policy**: `SECURITY.md`
- **Architecture Overview**: `docs/ARCHITECTURE.md`
- **Setup Guide**: `docs/SETUP.md`

---

## Appendix: Production Checklist

### Go-Live Checklist

- [ ] All infrastructure prerequisites met
- [ ] Application deployed and verified
- [ ] Load balancer configured with HTTPS
- [ ] Automated backups running successfully
- [ ] Monitoring and alerting configured
- [ ] Health checks passing
- [ ] Security hardening complete
- [ ] Rollback procedure tested
- [ ] Support team trained
- [ ] Documentation updated
- [ ] Go/No-Go decision approved

---

**Last Updated**: 2026-02-25  
**Version**: 1.0.0 (local-data-stack)
