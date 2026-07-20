"""HTTP request and response models for agent identity provisioning."""

from pydantic import BaseModel, Field


class ProvisionAgentIdentityRequest(BaseModel):
    """Authority and persona inputs approved by an administrator."""

    provisioning_id: str = Field(min_length=1, max_length=255)
    persona_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=100)
    realm_name: str = Field(min_length=1, max_length=255)
    realm_roles: list[str]
    groups: list[str]


class ProvisionedAgentIdentity(BaseModel):
    """Provisioned workload identity returned to its administrator."""

    provisioning_id: str
    persona_id: str
    namespace: str
    service_account: str
    spiffe_id: str
    keycloak_subject: str
    realm_roles: list[str]
    groups: list[str]
    policy_revision: str
    provenance_id: str
    forgejo_identity_id: int
