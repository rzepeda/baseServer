# Coding Standards

⚠️ **These standards are MANDATORY for AI development agents.**

## Core Standards

**Languages & Runtimes:**
- Python 3.12 - Required version
- Type hints mandatory for all function signatures
- Async-first for all I/O operations

**Style & Linting:**
- Formatter: `black` (100-character line length)
- Linter: `ruff` - must pass with no errors
- Type Checker: `mypy --strict` - must pass

**Test Organization:**
- Test file naming: `test_{module_name}.py`
- Test location: Unit tests in `tests/unit/`, integration in `tests/integration/`

## Critical Rules

**1. Logging: Never use print()**
```python
# ❌ WRONG
print("Transcript retrieved")

# ✅ CORRECT
logger.info("transcript_retrieved", video_id=video_id)
```

**2. Error Handling: Always include correlation_id**
```python
# ✅ CORRECT
raise InvalidURLError(url)  # Exception includes correlation_id
```

**3. Security: Never log sensitive data**
```python
# ❌ WRONG
logger.info("auth_attempt", token=bearer_token)

# ✅ CORRECT
logger.info("auth_attempt", token_hash=hashlib.sha256(bearer_token.encode()).hexdigest())
```

**4. Async/Await: All I/O operations must be async**
```python
# ✅ CORRECT
async def fetch_transcript(video_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
```

**5. Type Hints: All public functions must have complete type hints**
```python
# ✅ CORRECT
def parse_url(url: str) -> str:
    return extract_video_id(url)
```

**6. Configuration: Never hardcode secrets**
```python
# ✅ CORRECT
from src.config import get_config
config = get_config()
client_secret = config.oauth_client_secret
```

**7. Imports: Always use absolute imports**
```python
# ✅ CORRECT
from src.models.mcp import MCPRequest
from src.tools.base import BaseMCPTool
```

**8. Testing: All new code must have tests**
- Minimum 80% code coverage
- Tests for happy path, error cases, and edge cases

**9. Retry Logic: Only retry transient errors**
- Transient: Network timeouts, 429, 503
- Permanent: 400, 404, 401 - fail immediately

**10. Correlation ID: Thread through all function calls**
```python
# ✅ CORRECT
async def execute(params: dict, context: ToolExecutionContext):
    context.logger.info("tool_started")  # correlation_id included
```

---
