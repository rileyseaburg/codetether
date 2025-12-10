---
title: Production Checklist
description: Checklist for production deployments
---

# Production Checklist

Before deploying AgentMesh to production:

## Security

- [ ] Enable authentication (Keycloak or API tokens)
- [ ] Configure TLS certificates
- [ ] Set secure Redis password
- [ ] Review network policies

## Reliability

- [ ] Configure health checks
- [ ] Set up monitoring/alerting
- [ ] Configure backups for Redis/database
- [ ] Test failover scenarios

## Performance

- [ ] Configure resource limits
- [ ] Enable horizontal pod autoscaling
- [ ] Configure Redis persistence
- [ ] Review connection pooling

## Operations

- [ ] Set up logging aggregation
- [ ] Configure log retention
- [ ] Document runbooks
- [ ] Test disaster recovery
