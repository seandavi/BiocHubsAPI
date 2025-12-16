# Deployment Options Comparison

This document helps you choose the best deployment method for your BiocHubs API instance.

## Quick Comparison

| Feature | Cloud Run | Kubernetes | Docker | Local Dev |
|---------|-----------|------------|--------|-----------|
| **Setup Time** | 5 minutes | 20-30 minutes | 5 minutes | 2 minutes |
| **Complexity** | Low | High | Medium | Low |
| **Cost (monthly)** | $15-30 | $50-200+ | Variable | $0 |
| **Scalability** | Auto (0-1000+) | Manual/HPA | Manual | N/A |
| **Maintenance** | Minimal | Moderate-High | Low | N/A |
| **Best For** | Production | Enterprise | Small teams | Development |

## Detailed Comparison

### 1. Google Cloud Run ⭐ Recommended for Most Users

**Pros:**
- ✅ Fully managed, serverless
- ✅ Auto-scales to zero (no cost when idle)
- ✅ Built-in load balancing and TLS
- ✅ Pay only for what you use
- ✅ Quick deployments (< 2 minutes)
- ✅ Built-in monitoring and logging
- ✅ Easy rollbacks and traffic splitting
- ✅ Integrates seamlessly with Cloud SQL

**Cons:**
- ❌ Requires Google Cloud account
- ❌ Cold start latency (if scaled to zero)
- ❌ Vendor lock-in
- ❌ Request timeout limit (3600s max)

**When to Choose:**
- Production deployments
- Variable or unpredictable traffic
- Want minimal operational overhead
- Need automatic scaling
- Budget-conscious projects

**Getting Started:**
```bash
cp .env.cloudrun.example .env.cloudrun
# Edit .env.cloudrun
./cloudrun/deploy.sh
```

**Documentation:** [Cloud Run Guide](cloudrun/README.md) | [Quick Start](cloudrun/QUICKSTART.md)

---

### 2. Kubernetes

**Pros:**
- ✅ Full control over infrastructure
- ✅ Multi-cloud and on-premises support
- ✅ Advanced networking and security
- ✅ Rich ecosystem of tools
- ✅ No vendor lock-in
- ✅ Suitable for microservices architecture

**Cons:**
- ❌ Complex setup and maintenance
- ❌ Requires K8s expertise
- ❌ Higher operational overhead
- ❌ More expensive (always-on infrastructure)
- ❌ Manual scaling configuration

**When to Choose:**
- Enterprise environments
- On-premises deployments
- Multi-cloud strategy
- Complex microservices architecture
- Existing K8s infrastructure
- Need advanced networking/security

**Getting Started:**
```bash
just setup  # or kubectl apply -f k8s/
```

**Documentation:** [Kubernetes Guide](k8s/README.md)

---

### 3. Docker Standalone

**Pros:**
- ✅ Simple and straightforward
- ✅ Portable across environments
- ✅ Works anywhere Docker runs
- ✅ No cloud dependencies
- ✅ Easy to understand

**Cons:**
- ❌ No built-in scaling
- ❌ Manual load balancing
- ❌ Manual TLS/HTTPS setup
- ❌ Limited monitoring
- ❌ Requires manual updates

**When to Choose:**
- Small-scale deployments
- Single-server setups
- Testing/staging environments
- Development environments
- Quick prototypes

**Getting Started:**
```bash
docker build -t biochubs-api .
docker run -p 8000:8000 \
  -e POSTGRES_URI="postgresql://user:pass@host/db" \
  biochubs-api
```

---

### 4. Local Development

**Pros:**
- ✅ Instant startup
- ✅ Auto-reload on changes
- ✅ Easy debugging
- ✅ No deployment needed
- ✅ Works offline

**Cons:**
- ❌ Not production-ready
- ❌ Manual dependency management
- ❌ No isolation
- ❌ Single instance only

**When to Choose:**
- Active development
- Testing changes
- API exploration
- Learning the codebase

**Getting Started:**
```bash
uv sync
export POSTGRES_URI="postgresql://localhost/hubs_dev"
uv run hubs-api serve --reload
```

---

## Decision Tree

```
Do you need production deployment?
├─ No → Use Local Development
└─ Yes
   ├─ Have existing Kubernetes cluster?
   │  ├─ Yes → Use Kubernetes
   │  └─ No
   │     ├─ Need multi-cloud/on-premises?
   │     │  ├─ Yes → Use Kubernetes
   │     │  └─ No
   │     │     ├─ Comfortable with Google Cloud?
   │     │     │  ├─ Yes → Use Cloud Run ⭐
   │     │     │  └─ No → Use Docker or Kubernetes
   │     │     └─ Very small scale (<1000 req/day)?
   │     │        ├─ Yes → Use Docker
   │     │        └─ No → Use Cloud Run ⭐
   └─ Need advanced networking/security?
      ├─ Yes → Use Kubernetes
      └─ No → Use Cloud Run ⭐
```

## Cost Comparison

### Google Cloud Run
- **Free tier**: 2M requests/month, 360K GB-seconds/month
- **Typical small deployment**: $15-30/month
  - Cloud Run: $5-20/month
  - Cloud SQL (db-f1-micro): $7-10/month
- **Scales to zero**: No cost when idle

### Kubernetes
- **Minimum cost**: $50-200+/month
  - 3 nodes (basic): $50-100/month
  - Load balancer: $20/month
  - Storage: $10-20/month
- **Does not scale to zero**: Always paying for infrastructure
- **Higher at scale**: More predictable costs

### Docker Standalone
- **VPS hosting**: $5-20/month (DigitalOcean, Linode, etc.)
- **Database**: Self-hosted or external ($0-10/month)
- **Total**: $5-30/month
- **Note**: Single point of failure, no auto-scaling

### Local Development
- **Cost**: $0 (uses your computer)
- **Not suitable for production**

## Performance Comparison

### Latency

| Deployment | Cold Start | Warm Response | 99th Percentile |
|------------|------------|---------------|-----------------|
| Cloud Run | 1-3s* | 50-200ms | 300-500ms |
| Kubernetes | N/A | 50-150ms | 200-400ms |
| Docker | N/A | 50-150ms | 200-400ms |
| Local Dev | N/A | 30-100ms | 150-300ms |

*Cold start can be eliminated by setting min-instances=1

### Throughput

| Deployment | Max RPS (single instance) | Max Total RPS |
|------------|---------------------------|---------------|
| Cloud Run | ~100-200 | 10,000+ (auto-scale) |
| Kubernetes | ~100-200 | Depends on nodes |
| Docker | ~100-200 | Single instance limit |
| Local Dev | ~50-100 | Single instance limit |

## Feature Comparison

| Feature | Cloud Run | Kubernetes | Docker | Local |
|---------|-----------|------------|--------|-------|
| Auto-scaling | ✅ Built-in | ⚠️ Manual/HPA | ❌ No | ❌ No |
| Load balancing | ✅ Built-in | ✅ Available | ❌ Manual | ❌ No |
| TLS/HTTPS | ✅ Built-in | ⚠️ Cert-manager | ❌ Manual | ❌ No |
| Zero downtime deploys | ✅ Yes | ✅ Yes | ❌ Manual | ❌ No |
| Health checks | ✅ Automatic | ✅ Configurable | ⚠️ Manual | ❌ No |
| Monitoring | ✅ Built-in | ⚠️ Manual setup | ❌ Manual | ❌ No |
| Logging | ✅ Built-in | ⚠️ Manual setup | ⚠️ Basic | ✅ Console |
| Secrets management | ✅ Secret Manager | ✅ K8s Secrets | ⚠️ Env vars | ⚠️ Env vars |
| Database migration | ⚠️ Manual | ✅ Jobs | ⚠️ Manual | ✅ Direct |
| Backup/restore | ✅ Cloud SQL | ✅ Available | ⚠️ Manual | ✅ Direct |
| Multi-region | ✅ Easy | ✅ Complex | ❌ No | ❌ No |
| CI/CD integration | ✅ Easy | ✅ Available | ✅ Easy | ❌ Not needed |

Legend:
- ✅ Fully supported / Easy
- ⚠️ Requires manual setup / Some complexity
- ❌ Not supported / Difficult

## Migration Paths

### From Local Dev → Production

1. **Quick production**: Local Dev → Cloud Run (fastest path to production)
2. **Controlled growth**: Local Dev → Docker → Cloud Run/Kubernetes
3. **Enterprise**: Local Dev → Kubernetes (if infrastructure exists)

### From Docker → Cloud Run

Very straightforward:
1. Push image to Artifact Registry
2. Deploy with `gcloud run deploy`
3. Point DNS to Cloud Run URL

### From Cloud Run → Kubernetes

More complex migration:
1. Export Cloud Run configuration
2. Create Kubernetes manifests
3. Set up ingress and services
4. Migrate database if needed
5. Update DNS

### From Kubernetes → Cloud Run

Simplification path:
1. Build and push image
2. Export environment variables
3. Deploy to Cloud Run
4. Test and switch DNS

## Recommendations by Use Case

### Startup/MVP
**→ Cloud Run** or Docker
- Reason: Quick to deploy, low cost, minimal maintenance

### Small Team (<10 users)
**→ Cloud Run** or Docker
- Reason: Focus on product, not infrastructure

### Growing Service (100-10K users)
**→ Cloud Run**
- Reason: Auto-scales, predictable costs, low maintenance

### Enterprise (10K+ users)
**→ Kubernetes** or Cloud Run
- Reason: More control, advanced features, compliance

### On-Premises Required
**→ Kubernetes**
- Reason: Only option for on-premises deployment

### Multi-Cloud Strategy
**→ Kubernetes**
- Reason: Portable across cloud providers

### Budget Constrained
**→ Docker** (on cheap VPS) or Cloud Run (free tier)
- Reason: Lowest operational costs

### High Compliance/Security
**→ Kubernetes** (own infrastructure) or Cloud Run (GCP compliance)
- Reason: Full control over security and compliance

## Support and Documentation

### Cloud Run
- [Official Docs](https://cloud.google.com/run/docs)
- [Local Guide](cloudrun/README.md)
- [Quick Start](cloudrun/QUICKSTART.md)
- Community: Large, active

### Kubernetes
- [Official Docs](https://kubernetes.io/docs/)
- [Local Guide](k8s/README.md)
- Community: Very large, active

### Docker
- [Official Docs](https://docs.docker.com/)
- Community: Very large, active

## Conclusion

**For most users, we recommend Google Cloud Run** as the best balance of:
- Ease of use
- Cost-effectiveness
- Scalability
- Reliability
- Maintenance burden

However, choose based on your specific requirements:
- **Enterprise/on-premises** → Kubernetes
- **Simple/small-scale** → Docker
- **Development** → Local Dev
- **Everything else** → Cloud Run ⭐

## Getting Help

- **General questions**: Open an issue on GitHub
- **Cloud Run specific**: See [cloudrun/README.md](cloudrun/README.md)
- **Kubernetes specific**: See [k8s/README.md](k8s/README.md)
- **Bug reports**: GitHub Issues
