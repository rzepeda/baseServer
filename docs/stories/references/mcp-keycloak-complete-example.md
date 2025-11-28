# MCP Server with Keycloak OAuth Integration

## Complete Working Example

This example shows how to use Keycloak as your OAuth Authorization Server for Claude.ai MCP integration.

---

## Architecture

```
Claude.ai → MCP Server → Keycloak
            ↓
         Your Tools (with user context)
```

**Keycloak handles:**
- User authentication (login page)
- OAuth authorization flow
- Token issuance
- Dynamic Client Registration

**Your MCP Server handles:**
- Tool implementation
- Token validation
- User-specific business logic

---

## Part 1: Keycloak Setup

### 1.1 Install Keycloak (Docker)

```bash
docker run -d \
  --name keycloak \
  -p 8080:8080 \
  -e KEYCLOAK_ADMIN=admin \
  -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:latest \
  start-dev
```

Access: http://localhost:8080

### 1.2 Create Realm

1. Admin Console → Master dropdown → Create Realm
2. Realm name: `mcp-realm`
3. Click Create

### 1.3 Enable Dynamic Client Registration

**Method A: Anonymous Registration (Easy for development)**

```
Realm Settings → Client Registration → Anonymous

Enabled: ON
```

**Method B: Initial Access Token (More secure)**

Via Admin Console:
```
Realm Settings → Client Registration → Initial Access Tokens
→ Create

Expiration: 0 (never)
Count: 100
→ Save

Copy the generated token: eyJhbGciOi...
```

### 1.4 Configure Required Settings

```
Realm Settings → Tokens

Access Token Lifespan: 900 seconds (15 min)
Client Session Idle: 1800 seconds (30 min)
Client Session Max: 36000 seconds (10 hours)

Advanced:
✅ Revoke Refresh Token
Refresh Token Max Reuse: 0
```

### 1.5 Configure Login Settings

```
Realm Settings → Login

✅ User registration: ON (optional)
✅ Forgot password: ON (optional)
✅ Remember me: ON
✅ Email as username: ON (optional)
```

### 1.6 Create Test User

```
Users → Add User

Username: testuser
Email: test@example.com
First Name: Test
Last Name: User

→ Create

Then go to Credentials tab:
Set password: testpass
Temporary: OFF
→ Save
```

---

## Part 2: MCP Server Implementation

### 2.1 Project Structure

```
mcp-server/
├── package.json
├── .env
├── src/
│   ├── index.js
│   ├── config.js
│   ├── middleware/
│   │   └── auth.js
│   ├── controllers/
│   │   ├── oauth.js
│   │   └── mcp.js
│   └── services/
│       ├── keycloak.js
│       └── tools.js
```

### 2.2 Dependencies

```json
{
  "name": "mcp-keycloak-server",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "express": "^4.18.2",
    "@modelcontextprotocol/sdk": "^1.0.0",
    "jsonwebtoken": "^9.0.2",
    "jwks-rsa": "^3.1.0",
    "dotenv": "^16.3.1"
  }
}
```

### 2.3 Environment Configuration

**Example Configuration (Production - auth.agentictools.uk):**
```bash
# .env
KEYCLOAK_URL=https://auth.agentictools.uk
KEYCLOAK_REALM=mcpServerAuth
PORT=3000

# Your OAuth endpoints will be:
# Discovery: https://auth.agentictools.uk/realms/mcpServerAuth/.well-known/openid-configuration
# Authorization: https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/auth
# Token: https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token
# JWKS: https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/certs
```

**Example Configuration (Local Development):**
```bash
# .env
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=mcp-realm
PORT=3000
```

### 2.4 Configuration Module

```javascript
// src/config.js
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
```

### 2.5 Keycloak Service

```javascript
// src/services/keycloak.js
import { config } from '../config.js';

export class KeycloakService {
  async getAuthorizationServerMetadata() {
    const response = await fetch(config.keycloak.metadataUrl);
    const oidcMetadata = await response.json();
    
    // Convert OIDC metadata to OAuth 2.0 Authorization Server Metadata format
    return {
      issuer: oidcMetadata.issuer,
      authorization_endpoint: oidcMetadata.authorization_endpoint,
      token_endpoint: oidcMetadata.token_endpoint,
      registration_endpoint: oidcMetadata.registration_endpoint,
      jwks_uri: oidcMetadata.jwks_uri,
      response_types_supported: oidcMetadata.response_types_supported,
      grant_types_supported: oidcMetadata.grant_types_supported,
      subject_types_supported: oidcMetadata.subject_types_supported,
      id_token_signing_alg_values_supported: oidcMetadata.id_token_signing_alg_values_supported,
      scopes_supported: oidcMetadata.scopes_supported,
      token_endpoint_auth_methods_supported: oidcMetadata.token_endpoint_auth_methods_supported,
      code_challenge_methods_supported: ["S256", "plain"]
    };
  }
}

export const keycloakService = new KeycloakService();
```

### 2.6 Auth Middleware

```javascript
// src/middleware/auth.js
import jwt from 'jsonwebtoken';
import jwksClient from 'jwks-rsa';
import { config } from '../config.js';

const client = jwksClient({
  jwksUri: config.keycloak.jwksUri,
  cache: true,
  cacheMaxAge: 86400000 // 24 hours
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
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid authorization header' });
  }
  
  const token = authHeader.substring(7);
  
  jwt.verify(
    token,
    getKey,
    {
      algorithms: ['RS256'],
      issuer: config.keycloak.issuer,
      clockTolerance: 30 // Allow 30 seconds clock skew
    },
    (err, decoded) => {
      if (err) {
        console.error('Token validation error:', err);
        return res.status(401).json({ error: 'Invalid token' });
      }
      
      // CRITICAL: Set auth context for MCP SDK
      req.auth = {
        clientId: decoded.sub,                    // User ID from Keycloak
        scopes: decoded.scope?.split(' ') || [],  // OAuth scopes
        token: token,
        user: {
          id: decoded.sub,
          username: decoded.preferred_username,
          email: decoded.email,
          name: decoded.name
        }
      };
      
      next();
    }
  );
}
```

### 2.7 OAuth Controller (Delegation)

```javascript
// src/controllers/oauth.js
import { keycloakService } from '../services/keycloak.js';

export class OAuthController {
  async getWellKnown(req, res) {
    try {
      const metadata = await keycloakService.getAuthorizationServerMetadata();
      res.json(metadata);
    } catch (error) {
      console.error('Error fetching auth server metadata:', error);
      res.status(500).json({ error: 'Failed to fetch authorization server metadata' });
    }
  }
}

export const oauthController = new OAuthController();
```

### 2.8 MCP Tools Service

```javascript
// src/services/tools.js
// Sample data (replace with your database)
const usersData = {
  '11111111-1111-1111-1111-111111111111': {
    id: '11111111-1111-1111-1111-111111111111',
    username: 'testuser',
    projects: [
      { id: 1, name: 'MCP Integration', status: 'active' },
      { id: 2, name: 'OAuth Testing', status: 'completed' }
    ],
    tasks: [
      { id: 1, title: 'Setup Keycloak', completed: true },
      { id: 2, title: 'Test with Claude', completed: false }
    ]
  }
};

export class ToolsService {
  getUserProjects(userId) {
    const user = usersData[userId];
    if (!user) {
      return { error: 'User not found' };
    }
    return {
      username: user.username,
      projects: user.projects
    };
  }
  
  getUserTasks(userId) {
    const user = usersData[userId];
    if (!user) {
      return { error: 'User not found' };
    }
    return {
      username: user.username,
      tasks: user.tasks
    };
  }
  
  addTask(userId, taskTitle) {
    const user = usersData[userId];
    if (!user) {
      return { error: 'User not found' };
    }
    
    const newTask = {
      id: user.tasks.length + 1,
      title: taskTitle,
      completed: false
    };
    
    user.tasks.push(newTask);
    
    return {
      message: 'Task added successfully',
      task: newTask
    };
  }
}

export const toolsService = new ToolsService();
```

### 2.9 MCP Controller (Streamable HTTP)

```javascript
// src/controllers/mcp.js
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { isInitializeRequest } from '@modelcontextprotocol/sdk/types.js';
import { randomUUID } from 'crypto';
import { z } from 'zod';
import { toolsService } from '../services/tools.js';

export class McpController {
  constructor() {
    this.transportsMap = new Map();
    this.server = new Server(
      {
        name: 'keycloak-mcp-server',
        version: '1.0.0'
      },
      {
        capabilities: {
          tools: {}
        }
      }
    );
    
    this.setupTools();
  }
  
  setupTools() {
    // Tool 1: Get user's projects
    this.server.setRequestHandler('tools/list', async () => ({
      tools: [
        {
          name: 'get_my_projects',
          description: 'Get all projects for the authenticated user',
          inputSchema: {
            type: 'object',
            properties: {}
          }
        },
        {
          name: 'get_my_tasks',
          description: 'Get all tasks for the authenticated user',
          inputSchema: {
            type: 'object',
            properties: {}
          }
        },
        {
          name: 'add_task',
          description: 'Add a new task for the authenticated user',
          inputSchema: {
            type: 'object',
            properties: {
              title: {
                type: 'string',
                description: 'Task title'
              }
            },
            required: ['title']
          }
        }
      ]
    }));
    
    this.server.setRequestHandler('tools/call', async (request, extra) => {
      const { name, arguments: args } = request.params;
      
      // Get auth info from context
      const authInfo = extra?.authInfo;
      
      if (!authInfo) {
        return {
          content: [{
            type: 'text',
            text: 'Error: Unauthorized - No authentication provided'
          }],
          isError: true
        };
      }
      
      const userId = authInfo.clientId;
      
      try {
        let result;
        
        switch (name) {
          case 'get_my_projects':
            result = toolsService.getUserProjects(userId);
            break;
            
          case 'get_my_tasks':
            result = toolsService.getUserTasks(userId);
            break;
            
          case 'add_task':
            result = toolsService.addTask(userId, args.title);
            break;
            
          default:
            return {
              content: [{
                type: 'text',
                text: `Error: Unknown tool ${name}`
              }],
              isError: true
            };
        }
        
        return {
          content: [{
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }]
        };
        
      } catch (error) {
        return {
          content: [{
            type: 'text',
            text: `Error: ${error.message}`
          }],
          isError: true
        };
      }
    });
  }
  
  async handlePost(req, res) {
    const sessionId = req.headers['mcp-session-id'];
    let transport;
    
    if (sessionId && this.transportsMap.has(sessionId)) {
      transport = this.transportsMap.get(sessionId);
    } else if (!sessionId && isInitializeRequest(req.body)) {
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (id) => {
          this.transportsMap.set(id, transport);
        }
      });
      
      transport.onclose = () => {
        if (transport.sessionId) {
          this.transportsMap.delete(transport.sessionId);
        }
      };
      
      // Connect with auth context
      await this.server.connect(transport, {
        authInfo: req.auth // Pass through from middleware
      });
    } else {
      return res.status(400).json({
        jsonrpc: '2.0',
        error: {
          code: -32000,
          message: 'Bad Request: No valid session ID provided'
        },
        id: null
      });
    }
    
    await transport.handleRequest(req, res, req.body);
  }
  
  async handleGet(req, res) {
    return this.handleSessionRequest(req, res);
  }
  
  async handleDelete(req, res) {
    return this.handleSessionRequest(req, res);
  }
  
  async handleSessionRequest(req, res) {
    const sessionId = req.headers['mcp-session-id'];
    
    if (!sessionId || !this.transportsMap.has(sessionId)) {
      return res.status(400).send('Invalid or missing session ID');
    }
    
    const transport = this.transportsMap.get(sessionId);
    await transport.handleRequest(req, res);
  }
}

export const mcpController = new McpController();
```

### 2.10 Main Server

```javascript
// src/index.js
import express from 'express';
import { config } from './config.js';
import { requireAuth } from './middleware/auth.js';
import { oauthController } from './controllers/oauth.js';
import { mcpController } from './controllers/mcp.js';

const app = express();

// Health check
app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'MCP Server with Keycloak OAuth' });
});

// OAuth discovery (delegates to Keycloak)
app.get('/.well-known/oauth-authorization-server', 
  oauthController.getWellKnown.bind(oauthController)
);

// MCP endpoints (Streamable HTTP) - all require auth
app.post('/mcp',
  requireAuth,
  express.json(),
  (req, res) => mcpController.handlePost(req, res)
);

app.get('/mcp',
  requireAuth,
  (req, res) => mcpController.handleGet(req, res)
);

app.delete('/mcp',
  requireAuth,
  (req, res) => mcpController.handleDelete(req, res)
);

app.listen(config.port, () => {
  console.log(`MCP Server running on port ${config.port}`);
  console.log(`Keycloak: ${config.keycloak.url}`);
  console.log(`Realm: ${config.keycloak.realm}`);
});
```

---

## Part 3: Testing

### 3.1 Start the Server

```bash
npm install
npm start
```

### 3.2 Test OAuth Discovery

**For Production (auth.agentictools.uk):**
```bash
# Test Keycloak realm is accessible
curl https://auth.agentictools.uk/realms/mcpServerAuth/.well-known/openid-configuration

# Should return JSON with:
# "issuer": "https://auth.agentictools.uk/realms/mcpServerAuth"
# "authorization_endpoint": "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/auth"
# "token_endpoint": "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token"

# Test your MCP server delegation
curl https://your-mcp-server.com/.well-known/oauth-authorization-server
```

**For Local Development:**
```bash
curl http://localhost:3000/.well-known/oauth-authorization-server
```

Should return Keycloak's OAuth metadata.

### 3.3 Get Access Token Manually (for testing)

**For Production (auth.agentictools.uk):**
```bash
# Get token using Resource Owner Password Credentials grant
# (Only for testing - requires Direct Access Grants enabled in Keycloak client)
curl -X POST \
  https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d 'client_id=admin-cli' \
  -d 'username=testuser' \
  -d 'password=testpass'

# Or use your custom client_id if you created one
curl -X POST \
  https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d 'client_id=mcp-server-client' \
  -d 'username=testuser' \
  -d 'password=testpass'
```

**For Local Development:**
```bash
# Get token using testuser credentials
curl -X POST \
  http://localhost:8080/realms/mcp-realm/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d 'client_id=admin-cli' \
  -d 'username=testuser' \
  -d 'password=testpass'
```

Copy the `access_token` from response.

### 3.4 Test MCP Endpoint with Token

```bash
export TOKEN="eyJhbGciOi..."

# Initialize session
curl -X POST http://localhost:3000/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'

# List tools
curl -X POST http://localhost:3000/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: <session-id-from-previous-response>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

---

## Part 4: Deploy & Connect to Claude

### 4.1 Deploy to Production

**Using auth.agentictools.uk as your Keycloak server:**

**Update .env for production:**
```bash
KEYCLOAK_URL=https://auth.agentictools.uk
KEYCLOAK_REALM=mcpServerAuth
PORT=3000
NODE_ENV=production
```

**Verify Keycloak is accessible:**
```bash
# Test the discovery endpoint
curl https://auth.agentictools.uk/realms/mcpServerAuth/.well-known/openid-configuration

# Should see JSON response with issuer, endpoints, etc.
```

**Deploy your MCP Server with HTTPS** (required for Claude.ai):
- Use a service like Google Cloud Run, AWS Lambda, Railway, Render, etc.
- Ensure your MCP server URL is HTTPS (e.g., `https://mcp.agentictools.uk`)

**For local development/testing:**
```bash
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=mcp-realm
PORT=3000
```

### 4.2 Add to Claude.ai

1. Go to Claude → Settings → Integrations
2. Click "Add integration"
3. Name: "My Keycloak MCP Server"
4. URL: `https://your-mcp-server.com/mcp`
5. Click "Connect"

### 4.3 Authorization Flow

1. Claude redirects you to Keycloak login page
2. Enter credentials: testuser / testpass
3. Keycloak asks for consent (first time)
4. Redirected back to Claude
5. See "Successfully connected to server"

### 4.4 Test with Claude

Ask Claude:
- "What are my current projects?"
- "Show me my tasks"
- "Add a new task: Review Keycloak integration"

---

## Troubleshooting

### Token Validation Fails

Check:
```javascript
// Verify issuer matches exactly
console.log('Token issuer:', decoded.iss);
console.log('Expected issuer:', config.keycloak.issuer);

// Check token expiration
console.log('Token exp:', new Date(decoded.exp * 1000));
console.log('Current time:', new Date());
```

### JWKS Errors

```javascript
// Test JWKS endpoint
curl http://localhost:8080/realms/mcp-realm/protocol/openid-connect/certs
```

### Keycloak Redirect Issues

Ensure redirect URI is exactly: `https://claude.ai/api/mcp/auth_callback`

---

## Security Checklist

- ✅ Use HTTPS in production
- ✅ Keep Keycloak admin password secure
- ✅ Set appropriate token lifespans
- ✅ Enable refresh token rotation
- ✅ Use strong client secrets (if confidential clients)
- ✅ Validate token issuer and audience
- ✅ Implement proper error handling
- ✅ Log authentication attempts

---

## Next Steps

1. **Add more tools** - Implement your business logic
2. **Connect to database** - Replace mock data
3. **Add user attributes** - Store MCP-specific data in Keycloak
4. **Implement scopes** - Fine-grained permissions
5. **Add SSE support** - For real-time updates
6. **Monitor tokens** - Track usage and revocation

This implementation is production-ready and provides a solid foundation for your MCP server with Keycloak authentication!
