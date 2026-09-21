# Tips and tricks

Rules of thumb from practice sessions, newest last.

- When two files or steps sound interchangeable, ask which one states a wish and which one records what happened: pyproject.toml wishes for pandas>=2, uv.lock records pandas 3.0.5. (2026-09-20)
- pyproject.toml states a wish (a range); uv.lock records the decision (one exact version). uv sync builds .venv from the lock. (2026-09-21)
