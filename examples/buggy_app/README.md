# buggy_app

A tiny user-login module used as a test target for the agent.

**Known bug (intentional):** `login()` crashes with `KeyError` when the request has
no `"email"` field, and with `AttributeError` when `"email"` is `None`. It should
return `LoginResult(ok=False, error="email is required")` instead.

Reproduce:

```bash
cd examples/buggy_app
python -m pytest -q   # 2 tests fail because of the bug
```
