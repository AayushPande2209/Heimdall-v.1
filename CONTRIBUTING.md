# Contributing

Keep changes small and focused. Add or update tests for behavioral changes, and
run both test commands from the README before submitting work.

Do not commit datasets, recordings, credentials, or model weights. Hardware-only
imports must remain lazy or be skipped/mocked so development and CI work without
a Raspberry Pi. Document decisions that affect formats, hardware interfaces, or
model behavior in `docs/decisions.md`.

Do not copy ADIAT or other GPL-licensed implementation code into this Apache-2.0
codebase. Check license compatibility and provenance before adapting third-party
code. Footage contributed by friends or volunteers requires documented consent
before it is used in a released dataset or redistributed model.
