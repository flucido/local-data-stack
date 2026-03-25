# ⚠️ ARCHIVED - Kubernetes Manifests

> **This directory was archived in February 2026.**

## Why Kubernetes Was Archived

Kubernetes is **overkill for the OSS Framework target audience** (school districts with 100-5,000 students).

### Docker Compose is Sufficient
- ✅ Single-server deployment
- ✅ All needed features (health checks, volumes, networking)
- ✅ Lower operational complexity
- ✅ Better local development = production parity
- ✅ Aligned with project goal: **"simple deployment"**

### K8s Operational Burden
- Requires 3+ nodes for HA
- Steep learning curve
- Regular security patches and upgrades
- Higher operational cost

## Current Deployment Path

The **canonical deployment** is:
- **Location**: `oss_framework/deployment/metabase/docker-compose.yml`
- **Features**: DuckDB driver built-in, proper volume mounts, health checks

## How to Restore (If Needed)

```bash
# Restore directory
git mv oss_framework/k8s-archived oss_framework/k8s

# Then update manifests:
# - Add DuckDB driver support (not in archived version)
# - Update image versions
# - Test in development cluster
```

---

# 📖 Original Documentation (Below)

*The following is the original K8s deployment guide preserved for reference.*

---

# Kubernetes Deployment Guide - OSS Framework SIS Analytics

## Overview

This Kubernetes setup provides production-grade deployment for the OSS Framework SIS data pipeline with dashboards.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            Kubernetes Cluster (sis-analytics NS)            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          StatefulSet: PostgreSQL (1 replica)         │  │
│  │  - Persistent Volume: 50Gi                           │  │
│  │  - Service: postgres:5432 (headless + LB)           │  │
│  └──────────────────────────────────────────────────────┘  │
│         ▲            ▲            ▲           ▲             │
│         │            │            │           │             │
│  ┌──────┴────┐  ┌────┴──────┐  ┌─┴────────┐  ┌─┴──────────┐│
│  │Deployment:│  │Deployment:│  │Deployment:│ │Deployment:││
│  │ Pipeline  │  │ Grafana   │  │ Metabase  │ │ Superset   ││
│  │(2 replicas)  │(1 replica)   │(1 replica) │(1 replica) ││
│  │ HPA: 2-5  │  │PVC: 10Gi  │  │PVC: 5Gi   │ │PVC: 10Gi   ││
│  └───────────┘  └───────────┘  └───────────┘ └────────────┘│
│         │            │            │           │             │
│         └──────┬──────┴────────┬───┴───────────┴─────┘       │
│                │               │                            │
│           ConfigMaps, Secrets, RBAC, Networking             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster v1.20+
- kubectl CLI configured
- helm (optional, for advanced deployments)
- 10+ GB storage available
- 8+ GB RAM available
- Network connectivity between nodes

### Cloud Providers

Tested on:
- AWS EKS (elastic Kubernetes Service)
- Azure AKS (Azure Kubernetes Service)
- Google GKE (Google Kubernetes Engine)
- Local Minikube/Kind

## Quick Start

### 1. Create Namespace and Secrets

```bash
kubectl apply -f k8s/00-namespace-configmap-secrets.yaml

kubectl config set-context --current --namespace=sis-analytics
```

### 2. Create Storage Classes (if needed)

```bash
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
allowVolumeExpansion: true
EOF
```

### 3. Deploy PostgreSQL

```bash
kubectl apply -f k8s/01-postgres-statefulset.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s
```

### 4. Deploy Pipeline

```bash
# First, build and push Docker image
docker build -f docker/Dockerfile.pipeline -t your-registry/sis-pipeline:latest .
docker push your-registry/sis-pipeline:latest

# Update image in deployment
sed -i 's|sis-pipeline:latest|your-registry/sis-pipeline:latest|g' k8s/02-pipeline-deployment.yaml

# Deploy
kubectl apply -f k8s/02-pipeline-deployment.yaml

# Wait for deployment
kubectl wait --for=condition=available --timeout=300s deployment/sis-pipeline
```

### 5. Deploy Dashboards

```bash
kubectl apply -f k8s/03-dashboards-deployment.yaml

# Wait for all deployments
kubectl wait --for=condition=available --timeout=600s deployment --all
```

### 6. Verify Deployment

```bash
kubectl get all -n sis-analytics

kubectl get pvc -n sis-analytics

kubectl get svc -n sis-analytics
```

## Access Services

### Port Forwarding (Development)

```bash
# PostgreSQL
kubectl port-forward -n sis-analytics svc/postgres 5432:5432

# Grafana
kubectl port-forward -n sis-analytics svc/grafana 3000:3000

# Metabase
kubectl port-forward -n sis-analytics svc/metabase 3001:3000

# Superset
kubectl port-forward -n sis-analytics svc/superset 8088:8088
```

### LoadBalancer (Production)

Services with LoadBalancer type are available externally:

```bash
kubectl get svc -n sis-analytics -o wide

# Access via external IP
http://<EXTERNAL-IP>:3000     # Grafana
http://<EXTERNAL-IP>:3001     # Metabase
http://<EXTERNAL-IP>:8088     # Superset
psql -h <EXTERNAL-IP> -p 5432 -U sis_admin  # PostgreSQL
```

## Configuration

### Update Secrets

```bash
kubectl edit secret postgres-credentials -n sis-analytics
kubectl edit secret grafana-credentials -n sis-analytics
kubectl edit secret superset-credentials -n sis-analytics
```

### Update ConfigMaps

```bash
kubectl edit configmap postgres-config -n sis-analytics
kubectl edit configmap pipeline-config -n sis-analytics
```

### Environment Variables

All configs are in k8s YAML files. Update before deploying:

```yaml
# k8s/00-namespace-configmap-secrets.yaml
env:
- name: POSTGRES_PASSWORD
  value: "your-secure-password"
```

## Common Operations

### View Logs

```bash
# PostgreSQL logs
kubectl logs -f -n sis-analytics sts/postgres

# Pipeline logs
kubectl logs -f -n sis-analytics deployment/sis-pipeline -c pipeline

# Grafana logs
kubectl logs -f -n sis-analytics deployment/grafana
```

### Scaling

#### Manual Scaling

```bash
# Scale pipeline to 5 replicas
kubectl scale deployment sis-pipeline -n sis-analytics --replicas=5
```

#### Auto-scaling (HPA)

HPA is configured in `02-pipeline-deployment.yaml`:
- Scales between 2-5 replicas
- Based on CPU (70%) and memory (80%) utilization

```bash
# View HPA status
kubectl get hpa -n sis-analytics

# Edit HPA
kubectl edit hpa sis-pipeline-hpa -n sis-analytics
```

### Database Backup

```bash
# Backup database
kubectl exec -it -n sis-analytics postgres-0 -- pg_dump -U sis_admin sis_analytics > backup.sql

# Restore database
kubectl exec -it -n sis-analytics postgres-0 -- psql -U sis_admin sis_analytics < backup.sql
```

### Pod Shell Access

```bash
# Connect to PostgreSQL pod
kubectl exec -it -n sis-analytics postgres-0 -- psql -U sis_admin -d sis_analytics

# Connect to pipeline pod
kubectl exec -it -n sis-analytics deployment/sis-pipeline -c pipeline -- bash
```

## Monitoring & Observability

### Pod Status

```bash
kubectl describe pod -n sis-analytics <pod-name>

kubectl top pod -n sis-analytics

kubectl top node
```

### Events

```bash
kubectl get events -n sis-analytics --sort-by='.lastTimestamp'
```

### Health Checks

```bash
# PostgreSQL readiness
kubectl get pod -n sis-analytics postgres-0 -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'

# Pipeline readiness
kubectl get deployment -n sis-analytics sis-pipeline -o jsonpath='{.status.conditions[?(@.type=="Available")].status}'
```

## Troubleshooting

### Pod Not Starting

```bash
kubectl describe pod -n sis-analytics <pod-name>
kubectl logs -n sis-analytics <pod-name>
```

### Storage Issues

```bash
kubectl get pvc -n sis-analytics
kubectl describe pvc -n sis-analytics <pvc-name>
```

### Connection Issues

```bash
# Test PostgreSQL connectivity
kubectl run -it --rm debug --image=postgres:16-alpine --restart=Never -n sis-analytics -- psql -h postgres -U sis_admin -d sis_analytics -c "SELECT 1"

# Verify DNS
kubectl run -it --rm debug --image=alpine --restart=Never -n sis-analytics -- nslookup postgres
```

### Resource Constraints

```bash
# Check node resources
kubectl describe node

# Check resource requests/limits
kubectl describe deployment -n sis-analytics sis-pipeline
```

## Advanced Configuration

### Custom Storage Class

```bash
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: pd.csi.storage.gke.io
parameters:
  type: pd-ssd
EOF
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sis-network-policy
  namespace: sis-analytics
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: sis-analytics
  egress:
  - to:
    - namespaceSelector: {}
```

### Pod Security Policies

```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: sis-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  runAsUser:
    rule: 'MustRunAsNonRoot'
  fsGroup:
    rule: 'RunAsAny'
  readOnlyRootFilesystem: false
```

## Production Checklist

- [ ] Update all secrets with strong passwords
- [ ] Configure LoadBalancer services with TLS
- [ ] Set up persistent volume snapshots for backup
- [ ] Configure pod disruption budgets
- [ ] Enable network policies
- [ ] Configure RBAC roles properly
- [ ] Set resource requests/limits
- [ ] Enable pod security policies
- [ ] Configure monitoring (Prometheus)
- [ ] Set up logging (Loki/ELK)
- [ ] Configure horizontal pod autoscaler
- [ ] Set up ingress with TLS termination

## Upgrade & Rollback

### Rolling Update

```bash
# Trigger rolling update
kubectl set image deployment/sis-pipeline sis-pipeline=your-registry/sis-pipeline:v2.0 -n sis-analytics

# Monitor rollout
kubectl rollout status deployment/sis-pipeline -n sis-analytics

# Rollback if needed
kubectl rollout undo deployment/sis-pipeline -n sis-analytics
```

## Performance Tuning

### Database Optimization

```sql
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET work_mem = '10MB';
SELECT pg_reload_conf();
```

### Pod Resources

Adjust in YAML:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

## Cost Optimization

- Use spot instances for non-critical workloads (pipeline)
- Configure cluster auto-scaler
- Use StatefulSets for stateful workloads (PostgreSQL)
- Right-size container resources
- Use lifecycle policies for PVCs

## Support & Documentation

- [Kubernetes Docs](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [StatefulSet Guide](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
