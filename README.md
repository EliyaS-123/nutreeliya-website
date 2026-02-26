# geo-poisoning-project

Geo poisoning research project.

## Setup with uv

[uv](https://docs.astral.sh/uv/) is used for dependency and environment management.

```bash
# Create virtual environment and install dependencies
uv sync

# Run the project
uv run python main.py
# or
uv run main.py
```

## Adding dependencies

```bash
# Add a dependency (updates pyproject.toml and lockfile)
uv add <package>

# Add a dev dependency
uv add --dev <package>
```

## Python version

The project uses Python 3.11+. The version is pinned in `.python-version` for uv.
