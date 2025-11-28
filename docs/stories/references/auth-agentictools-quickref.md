# Quick Reference: auth.agentictools.uk Configuration

## Your Keycloak Setup

**Keycloak Server:** https://auth.agentictools.uk
**Realm Name:** mcpServerAuth
**Admin Console:** https://auth.agentictools.uk/admin

---

## All Your OAuth Endpoints

```bash
# Base URL
https://auth.agentictools.uk/realms/mcpServerAuth

# OAuth Discovery (what Claude fetches first)
https://auth.agentictools.uk/realms/mcpServerAuth/.well-known/openid-configuration

# Authorization Endpoint (login page)
https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/auth

# Token Endpoint (code exchange)
https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token

# JWKS Endpoint (public keys for JWT validation)
https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs

# Registration Endpoint (Dynamic Client Registration)
https://auth.agentictools.uk/realms/mcpServerAuth/clients-registrations/openid-connect
```

---

## Environment Variables for Your MCP Server

Create a `.env` file:

```bash
# Keycloak Configuration
KEYCLOAK_URL=https://auth.agentictools.uk
KEYCLOAK_REALM=mcpServerAuth

# Server Configuration
PORT=3000
NODE_ENV=production

# These are auto-constructed from KEYCLOAK_URL and KEYCLOAK_REALM:
# KEYCLOAK_ISSUER=https://auth.agentictools.uk/realms/mcpServerAuth
# KEYCLOAK_JWKS_URI=https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs
# KEYCLOAK_AUTH_URL=https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/auth
# KEYCLOAK_TOKEN_URL=https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token
```

---

## Quick Verification Tests

### Test 1: Keycloak Discovery Endpoint
```bash
curl https://auth.agentictools.uk/realms/mcpServerAuth/.well-known/openid-configuration
```

**Expected response:**
```json
{
  "issuer": "https://auth.agentictools.uk/realms/mcpServerAuth",
  "authorization_endpoint": "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/auth",
  "token_endpoint": "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token",
  "jwks_uri": "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs",
  ...
}
```

### Test 2: Public Keys (JWKS)
```bash
curl https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs
```

**Expected response:**
```json
{
  "keys": [
    {
      "kid": "...",
      "kty": "RSA",
      "alg": "RS256",
      "use": "sig",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

### Test 3: Get Test Access Token
```bash
# Replace with your actual test user credentials
curl -X POST https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d 'client_id=admin-cli' \
  -d 'username=YOUR_TEST_USER' \
  -d 'password=YOUR_TEST_PASSWORD'
```

**Expected response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ii4uLiJ9...",
  "expires_in": 300,
  "refresh_expires_in": 1800,
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer"
}
```

### Test 4: Verify Your MCP Server Delegation
```bash
# Once your MCP server is running
curl https://YOUR-MCP-SERVER.com/.well-known/oauth-authorization-server
```

Should return the same metadata as Test 1 above.

---

## Configuration in Your Code

### src/config.js

```javascript
import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: process.env.PORT || 3000,
  keycloak: {
    url: process.env.KEYCLOAK_URL,
    realm: process.env.KEYCLOAK_REALM,
    issuer: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}`,
    jwksUri: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/protocol/openid-connect/certs`,
    authorizationUrl: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/protocol/openid-connect/auth`,
    tokenUrl: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/protocol/openid-connect/token`,
    metadataUrl: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/.well-known/openid-configuration`,
    registrationUrl: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/clients-registrations/openid-connect`
  }
};

// With your values, this becomes:
// issuer: "https://auth.agentictools.uk/realms/mcpServerAuth"
// jwksUri: "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs"
// etc.
```

---

## JWT Token Validation

Your MCP server must validate tokens from Keycloak:

```javascript
import jwt from 'jsonwebtoken';
import jwksClient from 'jwks-rsa';

const client = jwksClient({
  jwksUri: 'https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs',
  cache: true,
  cacheMaxAge: 86400000
});

function getKey(header, callback) {
  client.getSigningKey(header.kid, (err, key) => {
    if (err) {
      callback(err);
      return;
    }
    const signingKey = key.getPublicKey();
    callback(null, signingKey);
  });
}

export function requireAuth(req, res, next) {
  const token = req.headers.authorization?.substring(7); // Remove "Bearer "
  
  jwt.verify(
    token,
    getKey,
    {
      algorithms: ['RS256'],
      issuer: 'https://auth.agentictools.uk/realms/mcpServerAuth',
      clockTolerance: 30
    },
    (err, decoded) => {
      if (err) {
        return res.status(401).json({ error: 'Invalid token' });
      }
      
      // Set auth context for MCP tools
      req.auth = {
        clientId: decoded.sub,
        scopes: decoded.scope?.split(' ') || [],
        token: token,
        user: {
          id: decoded.sub,
          username: decoded.preferred_username,
          email: decoded.email
        }
      };
      
      next();
    }
  );
}
```

---

## Connecting to Claude.ai

### Step 1: Ensure Both Servers Use HTTPS

- ✅ Keycloak: `https://auth.agentictools.uk`
- ✅ MCP Server: `https://YOUR-MCP-SERVER.com` (deploy to cloud)

### Step 2: Add Integration in Claude

1. Go to Claude → Settings → Integrations
2. Click "Add integration"
3. **Name:** "My MCP Server"
4. **URL:** `https://YOUR-MCP-SERVER.com/mcp`
5. Click "Connect"

### Step 3: OAuth Flow Happens

1. Claude fetches: `https://YOUR-MCP-SERVER.com/.well-known/oauth-authorization-server`
2. Your server returns Keycloak metadata
3. Claude redirects user to: `https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/auth`
4. User logs in via Keycloak
5. Keycloak redirects back to Claude with code
6. Claude exchanges code for tokens
7. Claude connects to your MCP server with access token

---

## Common Issues & Solutions

### Issue: "Invalid issuer"
**Solution:** Ensure `issuer` in JWT validation matches exactly:
```javascript
issuer: 'https://auth.agentictools.uk/realms/mcpServerAuth'
```

### Issue: "JWKS endpoint not accessible"
**Test:**
```bash
curl https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs
```
Should return public keys.

### Issue: "Token validation fails"
**Debug:**
```javascript
// Decode token without verification to inspect
const decoded = jwt.decode(token, { complete: true });
console.log('Token header:', decoded.header);
console.log('Token payload:', decoded.payload);
console.log('Expected issuer:', 'https://auth.agentictools.uk/realms/mcpServerAuth');
console.log('Actual issuer:', decoded.payload.iss);
```

### Issue: "Redirect URI mismatch"
**Solution:** In Keycloak client configuration, add:
```
https://claude.ai/api/mcp/auth_callback
https://claude.com/api/mcp/auth_callback
```

---

## Security Checklist

- ✅ HTTPS for all URLs (Keycloak and MCP server)
- ✅ Validate JWT signature with JWKS
- ✅ Validate issuer matches exactly
- ✅ Check token expiration (`exp` claim)
- ✅ Verify token hasn't been used before (optional)
- ✅ Set appropriate CORS headers
- ✅ Use environment variables for secrets
- ✅ Enable refresh token rotation in Keycloak
- ✅ Set appropriate token lifespans (15 min access, 30 day refresh)

---

## Quick Deployment Checklist

1. ✅ Keycloak realm created: `mcpServerAuth`
2. ✅ Test user created in Keycloak
3. ✅ Dynamic Client Registration enabled
4. ✅ MCP server deployed with HTTPS
5. ✅ Environment variables configured
6. ✅ Discovery endpoint working: `curl https://YOUR-MCP-SERVER.com/.well-known/oauth-authorization-server`
7. ✅ Token validation working
8. ✅ Test connection in Claude.ai

---

## Support Resources

**Keycloak Documentation:**
- OAuth/OIDC: https://www.keycloak.org/docs/latest/securing_apps/
- Admin REST API: https://www.keycloak.org/docs-api/latest/rest-api/

**Your Endpoints:**
- Admin Console: https://auth.agentictools.uk/admin
- Realm Discovery: https://auth.agentictools.uk/realms/mcpServerAuth/.well-known/openid-configuration

**Testing Tools:**
- JWT Decoder: https://jwt.io
- JWKS Inspector: https://8gwifi.org/jwkconvertfunctions.jsp
- OAuth Debugger: https://oauthdebugger.com

---

## Next Steps

1. Test all endpoints with curl commands above
2. Deploy your MCP server to a cloud platform
3. Configure Keycloak client settings
4. Add your MCP server URL to Claude.ai
5. Test the complete OAuth flow
6. Implement your custom MCP tools

Good luck! 🚀
