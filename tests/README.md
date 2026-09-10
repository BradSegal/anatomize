# Tests

This repo uses a small test pyramid with explicit pytest markers.

## Markers

- `unit`: fast, isolated tests (parsing, extraction, matching, config parsing).
- `integration`: filesystem-level tests (discovery, formatting, writing outputs).
- `e2e`: review CLI, MCP transport, executable documentation, and clean-package consumer behavior.

## Commands

```bash
python -m pytest
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m e2e
```

## Fixtures

- `tests/fixtures/research/mixed_project/`: Python/R source, notebooks, testthat, workflows, and captured tool results.
- `tests/fixtures/agentic_workflow/`: held-out review tasks with known definitions, consumers, tests, and documentation.
- `tests/fixtures/sessions/`: canonical portable-session artifacts.

Regression tests also construct temporary repositories for Python scopes and
import ambiguity, R lexical boundaries, changing source, symlink containment,
bounded artifact reads, and large inventories. These tests inspect R source
without executing it; they do not require an R runtime.
