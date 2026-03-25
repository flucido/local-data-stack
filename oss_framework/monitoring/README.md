# Monitoring & Logging Stack Documentation

Complete monitoring and logging solution for the OSS Framework SIS Analytics platform using Prometheus, Loki, Grafana, and ELK stack.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Quick Start](#quick-start)
5. [Prometheus Setup](#prometheus-setup)
6. [Loki Setup](#loki-setup)
7. [Grafana Dashboards](#grafana-dashboards)
8. [Alerting](#alerting)
9. [Log Aggregation](#log-aggregation)
10. [Performance Tuning](#performance-tuning)
11. [Troubleshooting](#troubleshooting)

---

## Overview

This monitoring stack provides comprehensive observability for the SIS Analytics platform:

- **Metrics**: Prometheus collects and stores time-series metrics
- **Logs**: Loki aggregates logs from all components
- **Visualization**: Grafana dashboards for real-time monitoring
- **Alerting**: Automated alerts for critical issues

### Key Features

- **Multi-Source Metrics**: Kubernetes, PostgreSQL, application, and node metrics
- **Centralized Logging**: All component logs in one place
- **Pre-Built Dashboards**: System, application, and business metrics
- **Alert Management**: 30+ alert rules with escalation
- **High Availability**: Replicated components for reliability
- **Scalable Architecture**: Handles thousands of metrics/logs per second

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Data Collection Layer                      │
├─────────────────────────────────────────────────────────────┤
│  Prometheus Exporters (Node, PostgreSQL, Application)        │
│  Application Metrics (Custom Instrumentation)                │
│  Container Logs (stdout/stderr)                              │
└────────────────┬──────────────────────────┬──────────────────┘
                 │                          │
        ┌────────▼────────┐        ┌────────▼────────┐
        │   Prometheus    │        │      Loki       │
        │   Time-Series   │        │   Log Storage   │
        │    Database     │        │   & Indexing    │
        └────────┬────────┘        └────────┬────────┘
                 │                          │
        ┌────────▼──────────────────────────▼────────┐
        │          Grafana Dashboards                │
        │  (Visualization & Querying)                │
        └────────┬─────────────────────────────────┘
                 │
        ┌────────▼──────────────────────────┐
        │     Alertmanager                  │
        │  (Alert Routing & Management)     │
        └───────────────────────────────────┘
```

---

## Components

### Prometheus

**Purpose**: Time-series metric collection and storage

**Configuration**:
- Global scrape interval: 15s
- Retention: 15 days
- Storage: 20Gi PVC
- Replicas: 2

**Scrape Targets**:
- Kubernetes API server, nodes, kubelet
- Application pods (annotations-based)
- PostgreSQL exporter
- Node exporter
- Custom application metrics

**Files**:
- `prometheus-config.yml`: Scrape configurations
- `alerts.yml`: 30+ alert rules
- `recording_rules.yml`: Pre-computed metrics

### Loki

**Purpose**: Log aggregation and storage

**Configuration**:
- Log retention: 168 hours (7 days)
- Storage backend: S3 or cloud provider
- Replication: 3 replicas
- Query concurrency: 20

**Features**:
- Label-based indexing (efficient querying)
- Stream-based log processing
- Automatic schema evolution
- Multi-tenancy support

**Files**:
- `loki-config.yml`: Loki configuration
- `loki-k8s.yaml`: Kubernetes deployment

### Grafana

**Purpose**: Metrics and logs visualization

**Dashboards**:
- System metrics (CPU, memory, disk, network)
- Application performance (latency, errors, throughput)
- Database metrics (connections, queries, performance)
- Logging dashboard (log levels, sources, patterns)
- Alerting dashboard (active alerts, history)

**Data Sources**:
- Prometheus: Metrics
- Loki: Logs

### Alertmanager

**Purpose**: Alert routing and grouping

**Routing**:
- Critical alerts → PagerDuty + Email
- Warning alerts → Slack + Email
- Info alerts → Slack only

**Grouping**:
- By severity and job
- Wait time: 30 seconds
- Repeat interval: 4 hours

---

## Quick Start

### Prerequisites

- Kubernetes cluster (1.20+)
- 10Gi free storage for monitoring
- S3 or cloud storage for logs (optional)

### 1. Deploy Prometheus

```bash
kubectl apply -f oss_framework/monitoring/prometheus/prometheus-k8s.yaml
```

Verify:
```bash
kubectl get deployment -n sis-analytics prometheus
kubectl logs -n sis-analytics -l app=prometheus -f
```

Access:
```bash
kubectl port-forward -n sis-analytics svc/prometheus 9090:9090
# Visit: http://localhost:9090
```

### 2. Deploy Loki

```bash
kubectl apply -f oss_framework/monitoring/loki/loki-k8s.yaml
```

Verify:
```bash
kubectl get statefulset -n sis-analytics loki
kubectl logs -n sis-analytics -l app=loki -f
```

### 3. Configure Grafana Data Sources

```bash
# Port-forward to Grafana
kubectl port-forward -n sis-analytics svc/grafana 3000:3000

# Add Prometheus data source
# URL: http://prometheus:9090
# Type: Prometheus

# Add Loki data source
# URL: http://loki:3100
# Type: Loki
```

### 4. Import Dashboards

Pre-built dashboards:
- `dashboards/system-metrics.json`
- `dashboards/application-metrics.json`
- `dashboards/database-metrics.json`
- `dashboards/logs-dashboard.json`
- `dashboards/alerts-dashboard.json`

---

## Prometheus Setup

### Scrape Configuration

Add custom scrape targets via pod annotations:

```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
  labels:
    app: my-app
```

### Recording Rules

Pre-compute high-cardinality metrics:

```yaml
- record: instance:node_cpu_utilisation:rate1m
  expr: (100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])))) * 100
```

### Alert Rules

Define conditions for alerts:

```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"
```

---

## Loki Setup

### Log Labels

Critical labels for efficient querying:

```yaml
- key: namespace
  value: ${NAMESPACE}
- key: pod
  value: ${POD_NAME}
- key: container
  value: ${CONTAINER_NAME}
- key: level
  value: extract_level(message)
```

### Query Examples

```
# All error logs
{level="error"}

# Pipeline errors in production
{namespace="sis-analytics", pod=~"pipeline.*"} | json | level="ERROR"

# Database query duration > 1s
{job="postgres"} | json duration_ms > 1000

# Recent logs (last hour)
{namespace="sis-analytics"} | since=1h
```

---

## Grafana Dashboards

### System Metrics Dashboard

Displays:
- CPU utilization per node
- Memory usage
- Disk I/O
- Network throughput
- Network errors

### Application Dashboard

Displays:
- Request latency (p50, p95, p99)
- Error rate
- Request throughput
- Active connections
- Cache hit ratio

### Database Dashboard

Displays:
- Active connections
- Slow queries
- Transactions per second
- Cache hit ratio
- Backup status

### Logs Dashboard

Displays:
- Log volume by level
- Log volume by component
- Recent errors
- Log rate

---

## Alerting

### Alert Severity Levels

- **Critical**: Service outage, data corruption, security breach
- **Warning**: Degraded performance, high resource usage
- **Info**: Informational events, normal operations

### Alert Rules

30+ pre-defined rules:

**Kubernetes**:
- Node not ready
- Pod crash looping
- PVC usage > 80%
- PVC inodes > 95%

**Application**:
- High error rate (> 5%)
- High latency (p99 > 1s)
- Pipeline execution failure
- Data validation failure

**Database**:
- Down or unreachable
- Connection limit > 80%
- Slow queries detected
- Replication lag > 10s

**Infrastructure**:
- High CPU (> 80%)
- High memory (> 80%)
- High disk (> 80%)
- Network errors

---

## Log Aggregation

### Sources

- Application logs (Python, JSON)
- Kubernetes logs (events, audit)
- Database logs (PostgreSQL)
- System logs (kernel, service)

### Processing Pipeline

1. **Collection**: Container stdout/stderr
2. **Parsing**: Extract structured fields
3. **Labeling**: Add context labels
4. **Storage**: Index in Loki
5. **Querying**: LogQL queries in Grafana

### Retention

- Production: 7 days
- Staging: 3 days
- Development: 1 day

---

## Performance Tuning

### Prometheus

Optimize for scale:

```yaml
# Increase storage
storage_capacity: 100Gi

# Reduce scrape interval for less critical metrics
scrape_interval: 30s

# Use recording rules for complex queries
record: aggregated_metrics
expr: sum(rate(...))
```

### Loki

Optimize throughput:

```yaml
# Increase chunk size
max_chunk_size: 1000000  # 1MB

# Adjust index period
period: 24h

# Enable compression
compression: snappy
```

### Grafana

Query optimization:

```
# Use recording rules instead of queries
{__name__="aggregated_metric"}

# Limit time range
($__from to $__to)

# Sample data
| sample 100
```

---

## Troubleshooting

### Prometheus Not Scraping Targets

```bash
# Check Prometheus targets
curl http://prometheus:9090/api/v1/targets

# Verify pod annotations
kubectl get pods -o jsonpath='{.items[].metadata.annotations}'

# Check service discovery
kubectl logs -n sis-analytics -l app=prometheus | grep discovery
```

### Loki Queries Slow

```bash
# Check index cache
curl http://loki:3100/metrics | grep cache

# Verify storage backend
kubectl logs -n sis-analytics -l app=loki | grep storage

# Monitor query concurrency
curl http://loki:3100/metrics | grep query_concurrent
```

### High Disk Usage

```bash
# Check Prometheus retention
curl http://prometheus:9090/api/v1/status/tsdb

# Check Loki storage
kubectl exec -n sis-analytics loki-0 -- du -sh /loki

# Increase retention policies
# Edit Prometheus retention or Loki TTL
```

### Missing Metrics

```bash
# Verify scrape targets are up
curl http://prometheus:9090/api/v1/targets?state=active

# Check metric names
curl 'http://prometheus:9090/api/v1/label/__name__/values'

# Verify exporters are running
kubectl get pods -n sis-analytics | grep exporter
```

---

## Deployment Options

### Docker Compose

For development:
```bash
cd oss_framework/docker
docker-compose up prometheus loki grafana
```

### Kubernetes

For production:
```bash
# Apply manifests
kubectl apply -f oss_framework/monitoring/prometheus/prometheus-k8s.yaml
kubectl apply -f oss_framework/monitoring/loki/loki-k8s.yaml

# Verify deployment
kubectl get all -n sis-analytics -l app=prometheus,app=loki
```

### Helm Charts (Optional)

```bash
# Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack

# Loki
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack
```

---

## Security Considerations

1. **Network Policies**: Restrict traffic between components
2. **RBAC**: Service accounts with minimal permissions
3. **Secrets**: Store credentials in Kubernetes secrets
4. **TLS**: Enable TLS for all connections
5. **Authentication**: Protect Grafana with strong passwords
6. **Audit Logs**: Log all administrative actions

---

## Support Resources

- Prometheus Docs: https://prometheus.io/docs/
- Loki Docs: https://grafana.com/docs/loki/
- Grafana Docs: https://grafana.com/docs/grafana/
- AlertManager Docs: https://prometheus.io/docs/alerting/alertmanager/

---

**Last Updated**: January 26, 2024
