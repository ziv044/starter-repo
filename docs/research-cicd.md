# Research: CI/CD Infrastructure for pm6

**Date:** 2025-12-15
**Status:** Completed
**Decision:** GitHub Actions with pytest

---

## Requirements

- Free CI/CD solution
- Constant unit tests on push
- Prevent regressions from merging
- Python backend support

---

## Selected Solution: GitHub Actions

### Why GitHub Actions

| Feature | Value |
|---------|-------|
| Free minutes | 2,000/month (public: unlimited) |
| Self-hosted runners | Free & unlimited |
| Setup complexity | Low (YAML in repo) |
| Python support | Native matrix builds |

### Alternatives Considered

| Platform | Free Tier | Decision |
|----------|-----------|----------|
| GitLab CI | 400 min/mo | Less minutes |
| Jenkins | Unlimited (self-host) | Too much setup |
| CircleCI | 6,000 min/mo | Unnecessary complexity |

---

## Implementation Plan

### 1. GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest --cov=src tests/
```

### 2. Branch Protection Rules

- Require status checks to pass before merging
- Require pull request reviews (optional)
- No direct pushes to main

### 3. Testing Stack

- **pytest**: Test framework
- **pytest-cov**: Coverage reporting
- **pytest-asyncio**: For async Claude SDK code

---

## Future Considerations

- Self-hosted runner if exceeding free minutes
- Coverage thresholds (e.g., fail if < 80%)
- Integration tests for Claude API (mocked)

---

## Sources

- [Pytest with GitHub Actions Guide](https://pytest-with-eric.com/integrations/pytest-github-actions/)
- [Python CI/CD Pipeline Guide 2025](https://atmosly.com/blog/python-ci-cd-pipeline-mastery-a-complete-guide-for-2025/)
- [Best Open Source CI/CD Tools 2025](https://airbyte.com/top-etl-tools-for-sources/open-source-ci-cd-tools)
