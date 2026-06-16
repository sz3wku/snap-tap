## Summary

What changed?

## Validation

- [ ] `uv lock --check`
- [ ] `uv run pytest`
- [ ] `uv run ruff check src tests`
- [ ] `uv run mypy --explicit-package-bases src tests`
- [ ] `uv build --out-dir temp\build-check`

## Safety

- [ ] No raw screenshots, raw XML, typed private text, selectors, tokens, or private paths are exposed.
- [ ] Phone-touch changes go through primitive receipts.
- [ ] Live validation used explicit device ids.

## Notes

Anything reviewers should know?
