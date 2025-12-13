---
title: Production Checklist
description: Checklist for production deployments
---

# Production Checklist

Before deploying CodeTether to production:

## Security

- [ ] Enable authentication (Keycloak or API tokens)
- [ ] Configure TLS certificates
- [ ] Set secure Redis password
- [ ] Set secure PostgreSQL password
- [ ] Review network policies

## Reliability

- [ ] Configure health checks
- [ ] Set up monitoring/alerting
- [ ] Configure backups for PostgreSQL and Redis
- [ ] Test failover scenarios
- [ ] Configure PostgreSQL for durable persistence (`DATABASE_URL`)

## Performance

- [ ] Configure resource limits
- [ ] Enable horizontal pod autoscaling
- [ ] Configure Redis persistence
- [ ] Configure PostgreSQL connection pooling
- [ ] Review connection pooling

## Operations

- [ ] Set up logging aggregation
- [ ] Configure log retention
- [ ] Document runbooks
- [ ] Test disaster recovery
