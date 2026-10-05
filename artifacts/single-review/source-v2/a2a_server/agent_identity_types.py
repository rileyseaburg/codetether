"""Typed contracts for persona workload-identity provisioning."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadIdentity:
    """Kubernetes workload coordinates and their SPIFFE projection."""

    namespace: str
    service_account: str
    client_id: str
    username: str
    email: str
    spiffe_id: str


@dataclass(frozen=True)
class KeycloakIdentity:
    """Keycloak subject created for one workload service account."""

    subject: str
