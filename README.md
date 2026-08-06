# PantryPilot

A single-household grocery inventory and printable shopping-list application built with Flask and SQLite.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app run init-db
flask --app run run --debug
```

Create stores from `POST /api/stores`, then add inventory in the browser. Quantity changes are recorded transactionally. Items at or below their custom threshold (or the global threshold in Settings) appear in combined and store-specific PDF lists.

## Test

```bash
pytest
```
