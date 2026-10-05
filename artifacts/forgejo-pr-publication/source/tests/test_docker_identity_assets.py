"""Production-image contracts for workload identity authorization."""

from pathlib import Path


DOCKERFILE = Path(__file__).parents[1] / 'Dockerfile'


def test_production_image_copies_opa_role_catalog():
    """Identity provisioning needs the OPA role catalog at runtime."""
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')
    assert 'COPY --from=builder /app/policies /app/policies' in dockerfile
