# Config Loader

A small C++17 configuration loader used for AI coding workflow exercises.

The current implementation loads application configuration from a
`key=value` configuration file.

Supported keys:

- `host`
- `port`
- `debug`

## Build

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build
```