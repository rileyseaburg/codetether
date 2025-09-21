# A2A Server Helm Chart

This Helm chart deploys the A2A (Agent-to-Agent) Server with MCP (Model Context Protocol) support on Kubernetes.

## Features

- **Full A2A Server deployment** with enhanced MCP capabilities
- **Redis integration** (included or external)
- **Authentication support** with configurable tokens
- **Enterprise-ready features**:
  - TLS/HTTPS support via Ingress
  - Health checks and monitoring
  - Horizontal pod autoscaling
  - Pod disruption budgets
  - Network policies
  - Resource limits and requests
- **Multiple deployment environments** with example configurations
- **Observability** with Prometheus ServiceMonitor support

## Prerequisites

- Kubernetes 1.20+
- Helm 3.8+
- (Optional) Prometheus Operator for monitoring
- (Optional) NGINX Ingress Controller for external access

## Quick Start

### 1. Add Dependencies

```bash
cd chart/a2a-server
helm dependency build
```

### 2. Development Deployment

```bash
# Deploy with development configuration
helm install a2a-dev chart/a2a-server/ \
  --values chart/a2a-server/examples/values-dev.yaml \
  --namespace a2a-dev \
  --create-namespace
```

### 3. Production Deployment

```bash
# Deploy with production configuration
helm install a2a-prod chart/a2a-server/ \
  --values chart/a2a-server/examples/values-prod.yaml \
  --namespace a2a-prod \
  --create-namespace
```

## Configuration

### Core Application Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `app.name` | Agent name | `"Enhanced A2A Agent"` |
| `app.description` | Agent description | `"An A2A agent with MCP tool integration"` |
| `app.logLevel` | Log level (DEBUG, INFO, WARNING, ERROR) | `"INFO"` |
| `app.enhanced` | Enable enhanced MCP features | `true` |

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Image repository | `a2a-server` |
| `image.tag` | Image tag | `"latest"` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `8000` |
| `service.targetPort` | Container port | `8000` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `""` |
| `ingress.hosts` | Ingress hosts configuration | `[{host: "a2a-server.local", paths: [{path: "/", pathType: "Prefix"}]}]` |
| `ingress.tls` | TLS configuration | `[]` |

### Redis Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Deploy Redis with the chart | `true` |
| `redis.auth.enabled` | Enable Redis authentication | `false` |
| `externalRedis.host` | External Redis host (when redis.enabled=false) | `"redis-master"` |
| `externalRedis.port` | External Redis port | `6379` |
| `externalRedis.password` | External Redis password | `""` |

### Authentication

| Parameter | Description | Default |
|-----------|-------------|---------|
| `auth.enabled` | Enable authentication | `false` |
| `auth.tokens` | Authentication tokens map | `{}` |

Example authentication configuration:
```yaml
auth:
  enabled: true
  tokens:
    agent1: "secure-token-123"
    agent2: "secure-token-456"
```

### Resource Management

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.limits.cpu` | CPU limit | `500m` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `128Mi` |

### Autoscaling

| Parameter | Description | Default |
|-----------|-------------|---------|
| `autoscaling.enabled` | Enable HPA | `false` |
| `autoscaling.minReplicas` | Minimum replicas | `1` |
| `autoscaling.maxReplicas` | Maximum replicas | `100` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization | `80` |

### Monitoring

| Parameter | Description | Default |
|-----------|-------------|---------|
| `monitoring.serviceMonitor.enabled` | Enable Prometheus ServiceMonitor | `false` |
| `monitoring.serviceMonitor.interval` | Scrape interval | `30s` |

## Deployment Examples

### Development Environment

```bash
helm install a2a-dev chart/a2a-server/ \
  --values chart/a2a-server/examples/values-dev.yaml \
  --set image.tag=dev \
  --namespace development
```

### Staging Environment

```bash
helm install a2a-staging chart/a2a-server/ \
  --values chart/a2a-server/examples/values-staging.yaml \
  --set image.tag=staging \
  --namespace staging
```

### Production Environment

```bash
# First, create secrets for production
kubectl create secret generic a2a-server-prod-auth \
  --from-literal=A2A_AUTH_TOKENS="prod-agent1:$(openssl rand -base64 32),prod-agent2:$(openssl rand -base64 32)" \
  --namespace production

# Deploy with production configuration
helm install a2a-prod chart/a2a-server/ \
  --values chart/a2a-server/examples/values-prod.yaml \
  --set image.tag=1.0.0 \
  --namespace production
```

## Health Checks

The chart includes comprehensive health checks:

- **Startup Probe**: Checks if the application has started (30 attempts, 10s interval)
- **Liveness Probe**: Ensures the application is running (every 10s)
- **Readiness Probe**: Checks if the application is ready to serve traffic (every 5s)

All probes use the A2A Agent Card endpoint: `/.well-known/agent-card.json`

## Security Features

### Pod Security

- Runs as non-root user (UID 1000)
- Read-only root filesystem option
- Dropped capabilities
- Security context configuration

### Network Security

```yaml
networkPolicy:
  enabled: true
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
```

### Authentication

Enable authentication for production deployments:

```yaml
auth:
  enabled: true
  tokens:
    production-client: "your-secure-token"
```

Clients authenticate using the `Authorization` header:
```bash
curl -H "Authorization: Bearer your-secure-token" \
  https://a2a-api.yourdomain.com/.well-known/agent-card.json
```

## Monitoring and Observability

### Prometheus Integration

Enable ServiceMonitor for Prometheus scraping:

```yaml
monitoring:
  serviceMonitor:
    enabled: true
    namespace: monitoring
    interval: 30s
    labels:
      release: prometheus
```

### Logs

View application logs:
```bash
kubectl logs -f deployment/a2a-server -n <namespace>
```

## Upgrading

### Upgrade the Chart

```bash
helm upgrade a2a-server chart/a2a-server/ \
  --values your-values.yaml \
  --namespace <namespace>
```

### Rolling Updates

The chart supports rolling updates with zero downtime:

```bash
helm upgrade a2a-server chart/a2a-server/ \
  --set image.tag=new-version \
  --namespace <namespace>
```

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -l app.kubernetes.io/name=a2a-server -n <namespace>
```

### View Pod Logs

```bash
kubectl logs -l app.kubernetes.io/name=a2a-server -n <namespace>
```

### Check Service Endpoints

```bash
kubectl get endpoints a2a-server -n <namespace>
```

### Test Agent Card Endpoint

```bash
kubectl port-forward svc/a2a-server 8080:8000 -n <namespace>
curl http://localhost:8080/.well-known/agent-card.json
```

### Common Issues

1. **Redis Connection Issues**: Check Redis service status and configuration
2. **Authentication Failures**: Verify auth tokens are correctly configured
3. **Resource Limits**: Check if pods are being OOMKilled or CPU throttled

## Uninstalling

```bash
helm uninstall a2a-server -n <namespace>
```

To completely remove all resources including PVCs:
```bash
kubectl delete pvc -l app.kubernetes.io/instance=a2a-server -n <namespace>
```

## Development

### Testing the Chart

```bash
# Lint the chart
helm lint chart/a2a-server/

# Test template rendering
helm template test-release chart/a2a-server/ \
  --values chart/a2a-server/examples/values-dev.yaml

# Dry run installation
helm install test-release chart/a2a-server/ \
  --values chart/a2a-server/examples/values-dev.yaml \
  --dry-run
```

### Building Dependencies

```bash
cd chart/a2a-server
helm dependency build
```

## Support

For issues and questions:
- [GitHub Issues](https://github.com/rileyseaburg/A2A-Server-MCP/issues)
- [A2A Protocol Documentation](https://a2aproject.github.io/A2A)

## License

This chart is licensed under the same license as the A2A Server project.