"""Import the edited server modules inside the exact built production image."""
import a2a_server.monitor_api
import a2a_server.policy_middleware
import a2a_server.worker_auth
import a2a_server.spiffe_auth
import a2a_server.task_metadata_trust
import a2a_server.keycloak_audience

print("Built server image imports OK")