This is the repository for a bluesky virtual person powered by LLMs and exposed to the web.

This is a python project that uses `uv` as python package manager, `fastapi` and is inspired by `https://tangled.sh/@cameron.pfiffer.org/void`, `https://github.com/haileyok/penelope`, and `https://github.com/PrefectHQ/marvin/tree/main/examples/slackbot` (tangled is github on atproto, you can git clone tangled.sh repos). These projects should be cloned to the `.eggs` directory, along with any other resources that are useful but not worth checking into the repo. We should simply common commands and communicate dev workflows by using a `justfile`.

Work from repo root whenever possible.

## Project Structure

- `src/` - The source code for the project.
- `tests/` - The tests for the project.
- `sandbox/` - place to experiment and aggregate context for specific tasks within the project.