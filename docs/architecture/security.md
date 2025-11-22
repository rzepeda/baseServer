# Security

⚠️ **These security requirements are MANDATORY.**

## Input Validation

**Validation Library:** Pydantic

**Validation Location:** API boundary (before processing)

**Rules:**
- All external inputs MUST be validated
- Validation at API boundary (not deep in code)
- Whitelist approach (not blacklist)
- URL validation with strict regex
- Parameter type validation (no `Any` for user inputs)

## Authentication & Authorization

**Auth Method:** OAuth 2.0 Bearer Token Validation

**Session Management:** Stateless (token-based)

**Patterns:**
- OAuth middleware enforces all tool requests
- Token validation with 500ms timeout (NFR14)
- Token validation results cached (60s TTL)
- Invalid tokens rejected with 401
- Health endpoint unauthenticated (K8s requirement)

## Secrets Management

**Development:** `.env` file (gitignored)

**Production:** Kubernetes Secrets

**Rules:**
- NEVER hardcode secrets
- Access via configuration service only
- No secrets in logs or error messages
- Pydantic `SecretStr` for secret fields
- Secret rotation procedure documented

## API Security

**HTTPS:** Enforced via Cloudflare Tunnel (TLS 1.2+)

**Request Size Limiting:** 10KB max (prevent DoS)

**Rate Limiting:** Phase 2 consideration

**CORS:** Disabled (server-to-server only)

## Data Protection

**Encryption in Transit:** HTTPS via Cloudflare Tunnel

**Encryption at Rest:** N/A (no persistent storage)

**PII Handling:** No PII stored or logged

**Logging Restrictions:**
- Never log OAuth tokens (hash only)
- Never log secrets
- Never log PII
- Sanitize all sensitive data

## Dependency Security

**Scanning:** `pip-audit` in CI pipeline

**Update Policy:** Monthly security updates

**Approval:** Review dependencies in PRs

**Pinning:** Exact versions in `requirements.txt`

## Security Testing

**SAST:** `bandit` (Python security analyzer)

**Secrets Detection:** `detect-secrets`

**Penetration Testing:** Manual security review

**Security Test Cases:**
- Authentication/authorization validation
- Input validation (SQL injection, XSS attempts)
- Data protection verification
- Dependency vulnerability scan

---
