# Contributing to Kore Memory

Thank you for your interest in contributing to Kore Memory! This guide will help you get started.

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **git**
- A Unix-like environment (macOS, Linux, WSL)

## Development Setup

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/kore-memory.git
   cd kore-memory
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[semantic,dev]"
   ```

3. **Verify the setup:**

   ```bash
   pytest tests/ -v
   ```

   All tests should pass before you start making changes.

## Running the Server Locally

```bash
kore                        # starts on localhost:8765
kore --port 9000 --reload   # dev mode with auto-reload
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_api.py -v

# Run a specific test class or method
pytest tests/test_api.py::TestSave -v
pytest tests/test_api.py::TestSave::test_save_basic -v
```

Tests use an in-process FastAPI TestClient (no network required) with a temporary SQLite database.

## Code Style

- **Formatter/Linter:** [ruff](https://docs.astral.sh/ruff/)
- **Line length:** 120 characters
- **Type hints:** Required for all public functions
- **Docstrings:** Required for all public classes and functions

Run the linter before committing:

```bash
ruff check .
ruff format .
```

## Submitting a Pull Request

1. **Create a feature branch** from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** with clear, focused commits.

3. **Ensure all tests pass:**

   ```bash
   pytest tests/ -v
   ```

4. **Ensure code style is clean:**

   ```bash
   ruff check .
   ruff format --check .
   ```

5. **Push your branch** and open a Pull Request against `main`.

6. **Describe your changes** in the PR using the pull request template. Include what changed, why, and how to test it.

## Reporting Issues

When opening an issue, please include:

- **A clear title** summarizing the problem or request.
- **Steps to reproduce** (for bugs) with the minimal code to trigger the issue.
- **Expected vs. actual behavior.**
- **Environment details:** Python version, OS, Kore Memory version (`python -c "import kore_memory; print(kore_memory.__version__)"`).
- **Logs or tracebacks** if available.

Use the provided issue templates (bug report / feature request) when possible.

## Project Structure

See [CLAUDE.md](CLAUDE.md) for a detailed architecture overview, module descriptions, and environment variable reference.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
