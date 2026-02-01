# Changelog

All notable changes to this project will be documented in this file.

## 0.2.0 - 2026-02-01

### Added
- Multi-source skeleton workflows via `.anatomize.yaml` (per-source `level`, output subdirectories, and shared defaults).
- `anatomize init --preset standard` to scaffold the common pattern “src detailed, tests minimal”.
- Config-driven `anatomize generate|validate|estimate` (single command operates on all configured outputs).

### Changed
- `.anatomize.yaml` schema now uses `sources: [{path, output, level, ...}]` and writes into a root `output` directory.

## 0.1.0 - 2026-01-31

### Added
- `anatomize generate`: deterministic skeleton maps (hierarchy/modules/signatures) with YAML/JSON/Markdown outputs and embedded schemas.
- `anatomize validate`: strict validation of skeleton outputs with optional `--fix`.
- `anatomize estimate`: token estimation for skeleton outputs.
- `anatomize pack`: deterministic review bundles with include/ignore filtering, dependency slicing, compression, and token diagnostics.
- Pack output formats: Markdown, plain text, JSON, XML, and JSONL (stream-friendly).
- Pack safety/limits: `--content-encoding`, `--max-output`, and `--split-output`.
- Pack slicing: forward dependency closure (`--entry --deps`), reverse import closure (`--reverse-deps`), and optional Pyright-backed `--uses` slicing.
- Pack hybrid mode: JSONL bundles with per-file `meta|summary|content` representations and deterministic `--fit-to-max-output` selection tracing.

### Infrastructure
- CI for linting, typechecking, tests, builds, and optional Pyright e2e verification.
