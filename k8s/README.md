# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the Bioconductor Hubs API.

## Prerequisites

- Kubernetes cluster (Docker Desktop, k3s, minikube, etc.)
- kubectl configured
- Docker image built: `docker build -t biochubs-api:latest .`

## Quick Start (Docker Desktop Kubernetes)

### 1. Update Secrets

Edit `secret.yaml` and update the database password:

```yaml
stringData:
  DB_PASSWORD: "your-secure-password"
  POSTGRES_URI: "postgresql://postgres:your-secure-password@postgres-service:5432/hubs_dev"
```

### 2. Deploy All Resources

```bash
# Apply all manifests
kubectl apply -f k8s/

# Or apply in order:
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
# kubectl apply -f k8s/ingress.yaml  # Optional
```

### 3. Wait for Pods to be Ready

```bash
# Watch pod status
kubectl get pods -n biochubs -w

# Check pod logs
kubectl logs -n biochubs deployment/biochubs-api
kubectl logs -n biochubs statefulset/postgres
```

### 4. Initialize Database

Once the pods are running, initialize the database:

```bash
# Get API pod name
POD_NAME=$(kubectl get pods -n biochubs -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')

# Initialize database schema
kubectl exec -n biochubs $POD_NAME -- uv run hubs-api db init

# Run migration (if you have SQLite files available)
# kubectl cp annotationhub.sqlite3 biochubs/$POD_NAME:/tmp/
# kubectl cp experimenthub.sqlite3 biochubs/$POD_NAME:/tmp/
# kubectl exec -n biochubs $POD_NAME -- uv run hubs-api db migrate --sqlite-ah /tmp/annotationhub.sqlite3 --sqlite-eh /tmp/experimenthub.sqlite3
```

### 5. Access the API

For LoadBalancer service (Docker Desktop):

```bash
# Get service URL
kubectl get svc -n biochubs biochubs-api-service

# Access the API
curl http://localhost/
curl http://localhost/api/v2/resources?limit=5
```

Open in browser:
- API Root: http://localhost/
- Interactive Docs: http://localhost/docs
- Health Check: http://localhost/health

## Scaling

Scale the API deployment:

```bash
# Scale to 3 replicas
kubectl scale deployment biochubs-api -n biochubs --replicas=3

# Auto-scale based on CPU
kubectl autoscale deployment biochubs-api -n biochubs --min=2 --max=10 --cpu-percent=80
```

## Monitoring

```bash
# Check resource usage
kubectl top pods -n biochubs
kubectl top nodes

# View logs
kubectl logs -n biochubs -l app=biochubs-api --tail=100 -f
kubectl logs -n biochubs -l app=postgres --tail=100 -f

# Describe resources
kubectl describe deployment biochubs-api -n biochubs
kubectl describe statefulset postgres -n biochubs
```

## Database Backup

```bash
# Backup PostgreSQL data
POD_NAME=$(kubectl get pods -n biochubs -l app=postgres -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n biochubs $POD_NAME -- pg_dump -U postgres hubs_dev > backup.sql

# Restore
kubectl exec -i -n biochubs $POD_NAME -- psql -U postgres hubs_dev < backup.sql
```

## Persistent Storage

The PostgreSQL StatefulSet uses a PersistentVolumeClaim (20Gi by default).

To view:
```bash
kubectl get pvc -n biochubs
kubectl describe pvc postgres-storage-postgres-0 -n biochubs
```

To increase storage (if your storage class supports it):
```bash
kubectl edit pvc postgres-storage-postgres-0 -n biochubs
# Update spec.resources.requests.storage
```

## Ingress Setup (Optional)

If using Ingress instead of LoadBalancer:

1. Install an Ingress Controller (nginx example):
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
```

2. Update `/etc/hosts`:
```
127.0.0.1 biochubs-api.local
```

3. Apply ingress:
```bash
kubectl apply -f k8s/ingress.yaml
```

4. Access: http://biochubs-api.local

## TLS/HTTPS (Optional)

Install cert-manager for automatic TLS certificates:

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer (example for Let's Encrypt)
# See cert-manager documentation
```

## Troubleshooting

### Pods not starting

```bash
kubectl describe pod -n biochubs <pod-name>
kubectl logs -n biochubs <pod-name>
```

### Database connection errors

```bash
# Check postgres is ready
kubectl exec -n biochubs statefulset/postgres -- pg_isready -U postgres

# Test connection from API pod
POD_NAME=$(kubectl get pods -n biochubs -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n biochubs $POD_NAME -- env | grep POSTGRES
```

### Image pull errors

For local images with Docker Desktop:
```bash
# Ensure imagePullPolicy is set to Never or IfNotPresent in api-deployment.yaml
# Images built with Docker Desktop are automatically available to K8s
```

## Cleanup

Remove all resources:

```bash
kubectl delete namespace biochubs

# Or delete individual resources
kubectl delete -f k8s/
```

**Note**: This will delete the persistent volume and all data!

## Production Considerations

For production deployments:

1. **Secrets Management**: Use Sealed Secrets, Vault, or cloud provider secret managers
2. **Monitoring**: Install Prometheus + Grafana
3. **Logging**: Use ELK stack or cloud logging
4. **Backups**: Automated database backups to S3/NFS
5. **High Availability**: Multiple PostgreSQL replicas (consider PostgreSQL operator)
6. **Resource Limits**: Adjust based on actual usage
7. **Network Policies**: Restrict pod-to-pod communication
8. **Pod Security**: Use Pod Security Policies/Admission
9. **TLS**: Enable HTTPS with cert-manager
10. **Rate Limiting**: Configure at ingress level
