# Test Strategy and Standards

## Testing Philosophy

**Approach:** Test-After with AI Agent Test Generation

**Coverage Goals:**
- Unit Tests: 80% minimum
- Integration Tests: Critical workflows
- E2E Tests: Manual with real Claude/MCP client

**Test Pyramid:**
- 70% Unit Tests (fast, isolated, mocked)
- 20% Integration Tests (multi-component)
- 10% E2E Tests (manual validation)

## Test Types

### Unit Tests

**Framework:** pytest 8.0+

**File Convention:** `tests/unit/test_{module_name}.py`

**Coverage:** 80% minimum per module

**Requirements:**
- Mock all external dependencies
- Use AAA pattern (Arrange, Act, Assert)
- Test happy path, error cases, edge cases
- Mark async tests with `@pytest.mark.asyncio`

**Example:**
```python
class TestYouTubeTool:
    def test_parse_youtube_url_standard_format(self, youtube_tool):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = youtube_tool.parse_url(url)
        assert result.video_id == "dQw4w9WgXcQ"
```

### Integration Tests

**Scope:** Multi-component interactions

**Location:** `tests/integration/`

**Test Infrastructure:**
- YouTube API: Real HTTP calls to known test videos
- OAuth Provider: Mock OAuth server
- MCP Protocol: Real HTTP requests

### E2E Tests

**Approach:** Manual testing (no automation in MVP)

**Test Cases:**
- Happy path with real Claude
- Error handling (invalid URL, no transcript)
- Remote access via Cloudflare Tunnel
- Performance validation (<5s response time)

## CI Integration

Tests run in GitHub Actions on every push/PR:
- Unit tests with coverage report
- Integration tests
- Coverage threshold check (≥80%)

---
