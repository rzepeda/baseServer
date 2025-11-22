# Infrastructure and Deployment

## Infrastructure as Code

**Tool:** Kubernetes YAML Manifests

**Location:** `/k8s` directory

**Approach:** Manifest-based IaC - Kubernetes resources defined as YAML files in version control

## Deployment Strategy

**Strategy:** Rolling Updates (Zero-Downtime Deployments)

**Configuration:**
- **Replicas:** 2 (minimum for zero-downtime)
- **Rolling Update:** maxUnavailable: 0, maxSurge: 1
- **Resource Limits:** 512MB memory, 500m CPU per pod (NFR6)
- **Health Probes:** Liveness (30s), Readiness (10s)

## CI/CD Platform

**Platform:** GitHub Actions

**CI Pipeline Stages:**
1. Run tests (pytest with coverage)
2. Run linters (ruff, black, mypy)
3. Build Docker image
4. Test Docker image health

**CD Pipeline Triggers:** Git tag creation (e.g., `v1.0.0`)

**CD Pipeline Stages:**
1. Build and tag Docker image
2. Push to Docker registry
3. Update Kubernetes manifest
4. Deploy to Kubernetes
5. Verify deployment

## Environments

### Development (Local)
- Docker Desktop with Kubernetes, or Minikube/k3s
- Environment variables via `.env` file
- Local port: `http://localhost:8080`

### Production
- Kubernetes cluster (2 MCP server pods, 1 tunnel pod)
- OAuth credentials: Kubernetes Secret
- Tunnel token: Kubernetes Secret
- Public URL: `https://mcp-server.yourdomain.com`
- Resource allocation: ~1.2GB memory total

## Rollback Strategy

**Primary Method:** Kubernetes Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/mcp-server

# Rollback to specific revision
kubectl rollout undo deployment/mcp-server --to-revision=3
```

**Recovery Time Objective (RTO):** 5 minutes

**Trigger Conditions:**
- Health check failures
- High error rate (>5%)
- Performance degradation (>5s response)
- Critical bug discovered

---
