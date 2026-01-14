# GitHub Configuration

This directory contains GitHub-specific configuration for CI/CD, dependency management, and automation.

## Directory Structure

```
.github/
├── workflows/
│   ├── test.yml              # Run tests on push/PR
│   ├── lint.yml              # Code quality checks
│   ├── security.yml          # Security scanning
│   ├── deploy-docs.yml       # Deploy MkDocs to GitHub Pages
│   ├── publish-pypi.yml      # Publish package to PyPI
│   ├── release.yml           # Create GitHub releases
│   └── WORKFLOWS.md          # Detailed workflow documentation
├── dependabot.yml            # Automated dependency updates
└── README.md                 # This file
```

## Quick Reference

### Workflows Overview

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **test.yml** | Push/PR | Test on Python 3.13-3.14, Ubuntu/macOS/Windows |
| **lint.yml** | Push/PR | Ruff linting, formatting, mypy type checking |
| **security.yml** | Push/PR/Weekly | Safety + Bandit security scans |
| **deploy-docs.yml** | Push to master (docs changes) | Deploy MkDocs to GitHub Pages |
| **release.yml** | Push tag `v*` | Create GitHub Release with changelog |
| **publish-pypi.yml** | GitHub Release | Publish to PyPI (or TestPyPI) |

### Release Process

```bash
# 1. Update version
vim pyproject.toml  # Change version = "0.0.2"

# 2. Commit and tag
git add pyproject.toml
git commit -m "chore: bump version to 0.0.2"
git tag v0.0.2

# 3. Push (triggers automated release)
git push origin master --tags

# 4. Automated steps:
# - release.yml creates GitHub Release
# - publish-pypi.yml publishes to PyPI
# - deploy-docs.yml updates documentation
```

### Testing Before Release

```bash
# Test locally
uv run pytest -m "not integration" -v
uv run ruff check src/ tests/
uv build

# Test PyPI publish (TestPyPI)
# Go to Actions → Publish to PyPI → Run workflow → Check "TestPyPI"

# Test docs deployment
uv pip install mkdocs-material
uv run mkdocs serve
```

## Dependabot

Configured to automatically create PRs for:
- **GitHub Actions updates**: Weekly
- **Python dependencies**: Weekly, grouped by dev/prod

Dependency PRs are labeled automatically and grouped to reduce noise.

## Setup Required

### First-time Setup

1. **GitHub Pages** (for docs):
   - Settings → Pages → Source: `gh-pages` branch
   - Docs URL: https://hello-world-bfree.github.io/extraction/

2. **PyPI Trusted Publishing** (for package deployment):
   - Visit: https://pypi.org/manage/account/publishing/
   - Add publisher:
     - Repository: `hello-world-bfree/extraction`
     - Workflow: `publish-pypi.yml`
     - Environment: `pypi`

3. **Codecov** (optional, for coverage reports):
   - Sign up at https://codecov.io
   - Add repository (no token needed for public repos)

### Environment Variables

No secrets needed! All workflows use automatic authentication:
- **PyPI**: OIDC trusted publishing
- **GitHub Pages**: `GITHUB_TOKEN` (automatic)
- **Codecov**: No token for public repos

## Documentation

For detailed workflow documentation, see [workflows/WORKFLOWS.md](workflows/WORKFLOWS.md).

Topics covered:
- Workflow triggers and behavior
- Setup instructions
- Deployment checklist
- Troubleshooting guide
- Local development commands

## Monitoring

### Build Status

Check workflow status:
- https://github.com/hello-world-bfree/extraction/actions

### Package Status

- **PyPI**: https://pypi.org/project/doc-extraction/
- **Docs**: https://hello-world-bfree.github.io/extraction/
- **Releases**: https://github.com/hello-world-bfree/extraction/releases

## Support

For issues with workflows:
1. Check [workflows/WORKFLOWS.md](workflows/WORKFLOWS.md) troubleshooting section
2. Review workflow logs in GitHub Actions tab
3. Open issue at https://github.com/hello-world-bfree/extraction/issues
