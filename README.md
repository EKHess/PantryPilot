# PantryPilot

A responsive Flask prototype for tracking household grocery inventory. This
first version focuses on the application shell and mockup-matched static views,
while retaining a routes → services → database architecture for future work.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

Visit <http://127.0.0.1:5000>. Run tests with `pytest`.
