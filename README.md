# SkyTwin

A spacecraft digital twin that answers two questions:

- **Live Mode**: *what is happening right now?* Telemetry is compared against the twin's physics every tick,
  so faults are flagged when the spacecraft stops behaving like the model, often before a limit is crossed.
- **Simulation Mode**: *what would happen if…?* The operator picks a scenario ("+20% power", "comms lost for
  10 min", "+15 °C"). The twin copies the live state, propagates it forward in a sandbox and returns the predicted
  impact, risks with timing, and a plain-English explanation. Nothing is ever sent to the spacecraft.

Simulate → Evaluate → Operator decides.

## Quick start

```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
cd ../frontend && npm install && npm run build
cd ../backend && .venv/Scripts/python -m uvicorn skytwin.api.main:app --port 8000
# open http://localhost:8000
```

Optional NASA benchmark (SMAP/MSL labelled anomalies):
`python scripts/download_nasa.py && python scripts/validate_anomalies.py` from `backend/`.

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for all commands and architecture, and [docs/PLAN.md](docs/PLAN.md) for the plan and demo script.
