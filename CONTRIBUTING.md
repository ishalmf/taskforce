# Contributing

Contributions are welcome. Keep Taskforce local-first, lightweight, and unable to interfere with the coding agents it observes.

## Pull requests

1. Open an issue before substantial architectural changes.
2. Keep integrations isolated under `integrations/`.
3. Do not collect prompt or response content.
4. Add tests for integration protocol changes.
5. Run `npm test`, `npm run build`, `cargo fmt --check`, and `cargo test`.

New agent integrations should use official lifecycle hooks when available. Terminal scraping and global keyboard monitoring are intentionally out of scope.
