# Contributing

Thank you for your interest in improving this project.

## How to contribute

1. Open an issue to describe the bug or feature before large changes.
2. Fork the repository and create a branch from the default branch.
3. Follow existing code style: Python **3.11+** (see CI and `backend/Dockerfile`), Black-compatible formatting, flake8, mypy where applicable; frontend ESLint, TypeScript `type-check`, and `npm test`.
4. Add or update tests for behavior changes.
5. Run the test suites locally (`make test` or the commands in [README.md](README.md) and [TESTING_GUIDE.md](TESTING_GUIDE.md); backend often uses `pytest` with a coverage gate, frontend uses `npm run test:ci` in CI).
6. Update user-facing or contributor docs if your change affects how people run, configure, or operate the app.
7. Open a pull request with a clear description of the change and how you verified it.

## Security

Do not commit secrets, API keys, or production `.env` files. Use [backend/.env.example](backend/.env.example), [production.env.example](production.env.example), and [env.template](env.template) as references only.
