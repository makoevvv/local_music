# Local Music — Backend

FastAPI backend. See [`docs/13-development-guide.md`](../docs/13-development-guide.md) for setup.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
