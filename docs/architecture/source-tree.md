# Source Tree

```
youtubeagenttranscript/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── docs/
│   ├── architecture.md
│   ├── prd.md
│   ├── DEPLOYMENT.md
│   └── DEVELOPMENT.md
│
├── k8s/
│   ├── base/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── secret.yaml.example
│   ├── cloudflare-tunnel/
│   │   ├── deployment.yaml
│   │   ├── configmap.yaml
│   │   └── secret.yaml.example
│   └── kustomization.yaml
│
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── server.py
│   ├── config.py
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── oauth.py
│   │
│   ├── registry/
│   │   ├── __init__.py
│   │   └── tool_registry.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── youtube_tool.py
│   │   └── _template_tool.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── mcp.py
│   │   ├── auth.py
│   │   ├── errors.py
│   │   └── youtube.py
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── health.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── errors.py
│       └── cache.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   │
│   ├── unit/
│   │   ├── test_youtube_tool.py
│   │   ├── test_tool_registry.py
│   │   ├── test_oauth_middleware.py
│   │   └── test_error_handling.py
│   │
│   ├── integration/
│   │   ├── test_mcp_workflow.py
│   │   ├── test_oauth_flow.py
│   │   └── test_youtube_api.py
│   │
│   └── fixtures/
│       ├── mock_transcripts.json
│       └── mock_oauth_responses.json
│
├── scripts/
│   ├── setup-dev-env.sh
│   ├── run-local.sh
│   ├── create-k8s-secrets.sh
│   └── test-coverage.sh
│
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── README.md
└── CHANGELOG.md
```

---
