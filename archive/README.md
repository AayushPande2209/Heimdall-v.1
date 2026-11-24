# Temporary archive

This directory intentionally retains superseded pipeline/demo code, learning
exercises, and pre-restructure recorder backups. It is excluded from packaging
and test discovery.

As of 2026-11-24, a static dependency audit found no active import of these files;
the benchmark's synthetic generator lives at `sim/synthframes.py`. Keep the
archive until benchmark ownership is confirmed. Before removing it from `main`,
create a recoverable tag such as `archive-2026` and document the audit result.
