# Post-authentication issuer mismatch

- User-supplied Keycloak activity showed successful A2A sessions. The address
  `10.233.66.113` mapped to an A2A API pod, supporting server-mediated login.
- **Live deployment/Argo diagnostic:** service-client token requested through
  internal HTTP/port-forward had issuer
  `http://auth.quantum-forge.io:18888/realms/quantum-forge`.
- The same service client through public HTTPS had issuer
  `https://auth.quantum-forge.io/realms/quantum-forge`.
- The API was requesting tokens through internal HTTP while enforcing the
  public HTTPS issuer. Keycloak had a hostname-only KC_HOSTNAME setting, so the
  token issuer inherited request scheme/port. No user password was used to test.
- **Live deployment/Argo repair:** set `env.KEYCLOAK_URL` to public HTTPS and
  explicitly retained the public `env.KEYCLOAK_ISSUER` in the existing Argo app.
  Token validation was not disabled. `transport-repair.json` records the change.
- Deployment generation 205 rolled out; both new API pods were ready with zero
  restarts at inspection. `/v1/auth/status` reported the corrected URL.
- **Static/local:** `PYTHONPATH=. .venv/bin/pytest -q tests/test_keycloak_issuer.py`
  reported 3 passed. The initial invocation without PYTHONPATH failed collection.
- The native error mapper was amended so token-validation failures are not
  mislabeled as incorrect passwords. Its Xcode test attempt was **not-run**:
  compilation failed because the Mac disk was full. This UI edit is not shipped.
- The user must retry the existing app after reopening it. Successful sign-in
  with the user's credentials is not claimed; no sessions were signed out and no
  user password was entered, exposed, changed, or reset.

## In-pod confirmation

- **Live deployment/Argo:** both new API pods, `5b4b4867f7-4xm7b` and
  `5b4b4867f7-gpbfh`, performed HTTPX discovery and service-client token requests
  through the public URL: both HTTP 200 and both token issuers matched HTTPS.
- The negative comparison inside `4xm7b` using the previous exact internal URL
  returned discovery issuer `http://auth.quantum-forge.io:8080/realms/quantum-forge`
  and exited 1 with `Issuer mismatch`, as expected. No production env was changed.
- A preliminary urllib probe hit HTTP 403; HTTPX, the actual backend transport,