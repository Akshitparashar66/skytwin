# SkyTwin — Development guide

Spacecraft digital twin for an 18-hour hackathon. Two modes on one physics core:

- **Live Mode**: telemetry → twin → current state → anomaly detection (twin residuals + limit checks).
- **Simulation Mode (What-If Engine)**: operator scenario → sandboxed copy of the twin → predicted
  trajectory, impact chain, risks, narrative, recommendations. Never commands the spacecraft.

Plan, demo script and cut list: [PLAN.md](PLAN.md).

## Commands

All commands from the repo root. Windows paths shown; on macOS/Linux use `.venv/bin/python`.

```bash
# --- setup (once) ---
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt && cd ..
cd frontend && npm install && cd ..

# --- run (dev: two terminals, hot reload) ---
cd backend && .venv/Scripts/python -m uvicorn skytwin.api.main:app --reload --port 8000
cd frontend && npm run dev            # http://localhost:5173 (proxies /api and /ws to :8000)

# --- run (demo: one process) ---
cd frontend && npm run build && cd ../backend && .venv/Scripts/python -m uvicorn skytwin.api.main:app --port 8000
                                      # http://localhost:8000 serves the built UI

# --- deploy (Docker; Render blueprint in render.yaml) ---
docker build -t skytwin . && docker run -p 8000:8000 skytwin   # one instance only: live state is in memory

# --- test / lint (run all before calling anything done) ---
cd backend && .venv/Scripts/python -m pytest -q          # 57 tests, ~7 s
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
cd frontend && npx tsc -b && npm test                    # typecheck + vitest
cd frontend && npm run build

# --- NASA benchmark (optional; app works without it) ---
cd backend && .venv/Scripts/python scripts/download_nasa.py      # ~118 MB into backend/data/nasa/
cd backend && .venv/Scripts/python scripts/validate_anomalies.py # writes backend/data/validation_report.json
                                      # ~25 s statistical only; ~90 s first run with an LSTM model (residuals cached)

# --- LSTM detector (trained on Colab, see training/README.md) ---
python training/build_notebook.py     # regenerate the notebook after editing training/train_lstm.py
# smoke test (needs torch + onnx + onnxscript + onnxruntime; NOT in backend/.venv):
python training/train_lstm.py --data-dir training/data --out-dir training/out --epochs 1 --max-windows 5000
```

Single test: `.venv/Scripts/python -m pytest tests/test_whatif.py::test_comms_blackout_recovers -q`.
On Windows set `PYTHONIOENCODING=utf-8` when printing results that contain `°`/`→` to the console.

## Layout

```
backend/skytwin/
  config.py              SpacecraftParams (physical constants) + LIMITS (warn/crit) + FDIR thresholds
  twin/                  THE shared physics core — no I/O
    state.py             TwinState (integrated state) · Frame (one telemetry frame)
    perturbations.py     KINDS catalog, Perturbation, Modifiers, apply_effect / apply_impulse
    spacecraft.py        Spacecraft.step/advance/run/frame: orbit, power, battery, thermal, data, SAFE-mode FDIR
  whatif/                What-If engine
    engine.py            simulate(): baseline vs scenario vs 4-member ensemble; impacts, endurance, recovery
    risk.py              limit-crossing findings (likely / possible) → risk level
    narrative.py         plain-English explanation + recommendations
    scenarios.py         demo PRESETS + catalog()
  telemetry/
    detector.py          DynamicThresholdDetector (shared by Live Mode and the NASA benchmark)
    live.py              LiveTwin: truth model + sensor noise + one-step twin prediction → residual detectors, limits, alerts
  nasa/                  SMAP/MSL loader + benchmark (tune on SMAP, report on held-out MSL)
    lstm.py              LstmPredictor: runs backend/models/lstm_detector.onnx via onnxruntime (no torch in the backend);
                         predicts `horizon` steps past its window (from the model's .json)
    validation.py        methods = predictor (rolling mean | LSTM) → same DynamicThresholdDetector → scored per method
  api/                   FastAPI app (main.py) + pydantic request schemas
backend/models/          lstm_detector.onnx + .json (horizon 30; commit these; absent = statistical-only benchmark)
                         archive/ keeps earlier models (e.g. the horizon-1 Colab run) for reference
backend/scripts/         download_nasa.py, validate_anomalies.py
backend/tests/           test_twin, test_whatif, test_detection, test_lstm (tiny ONNX fixture), test_api
training/                train_lstm.py (PyTorch → ONNX), build_notebook.py → SkyTwin_LSTM_Training.ipynb, README.md
frontend/src/
  App.tsx                nav rail (Live/Simulation), header with mission clock, loads config/catalog/validation
  components/Icon, CardHeader   inline SVG icon set + shared card header
  hooks/useLiveTelemetry WebSocket client with reconnect backoff
  components/live/       stat tiles, charts, alerts, twin-vs-telemetry residuals, demo event panel, NASA card
  components/sim/        ScenarioBuilder, ResultView (risk banner, impact chain, charts, risks), CompareView
  components/TimeChart   the one Recharts wrapper (limits, eclipse shading, uncertainty band, tooltip)
  lib/                   format, series merging, colors (validated palette)
```

## Invariants — do not break

1. **One physics core.** Live Mode and What-If both use `twin.Spacecraft`. Never add a second model or a
   What-If-only shortcut; predictions must come from the same equations that track the live spacecraft.
2. **Sandbox is structural.** `simulate()` takes a `TwinState` snapshot and builds fresh `Spacecraft`s
   from it. It must never receive or mutate `LiveTwin`. `test_simulation_never_modifies_the_live_twin`
   and `test_simulate_does_not_touch_live_state` guard this.
3. **No command endpoint.** The only write to the live model is `POST /api/live/faults`, a clearly labelled
   demo that emulates a real-world event. The UI's "Send to spacecraft" button stays disabled.
4. **Snapshot on the event loop.** API handlers take `live.snapshot()` in the async handler, then run
   `simulate` in the threadpool, so a snapshot never interleaves with a live tick.
5. **Impacts are always scenario vs baseline from the same snapshot**, so orbital swings aren't reported as effects.
6. **Honest NASA numbers.** SMAP/MSL values are normalised and anonymised: use them to benchmark the
   detector, never to "calibrate" physics. Keep the tune-on-SMAP / report-on-MSL protocol.
7. **LSTM training never sees labels or test data.** It trains on `*_train.npy` only. Don't add test data or
   labels to training, and don't tune on MSL: pick models and thresholds by SMAP F1 only. The LSTM is
   benchmark-only: Live Mode stays on physics residuals.
8. **The notebook is generated.** Edit `training/train_lstm.py`, then run `build_notebook.py`.
9. **Keep the LSTM horizon > 1.** A 1-step predictor learns to copy the last value, so it tracks anomalies instead
   of exposing them (SMAP F1 0.51 → 0.67 going from horizon 1 to 30; held-out MSL 0.42 → 0.59).
10. **UI follows the SkyTwin Operations Console design**: nav rail, sticky header with mission clock, hairline cards,
   icons from `components/Icon.tsx`. Never add controls that imply commanding the spacecraft (e.g. an "Execute Command" button).

## Adding a scenario kind

1. `twin/perturbations.py`: add a `KindSpec` to `KINDS`; handle it in `apply_effect` (continuous) or
   `apply_impulse` (one-shot); add a field to `Modifiers` if needed and use it in `Spacecraft._derive`/`step`.
2. `api/schemas.py`: add the kind to the `Kind` literal.
3. `whatif/narrative.py`: add a sentence in `describe_perturbation`.
4. Optional: a preset in `whatif/scenarios.py`.
5. Tests: a physics test in `tests/test_twin.py` and an engine test in `tests/test_whatif.py`.
   The frontend picks new kinds up automatically from `/api/scenarios`.

## Tuning notes

- Model: 95-min LEO orbit, 35% eclipse, 140 W array, 82 W nominal load, 150 Wh battery. Baseline is
  power-positive by ~14 W orbit-average; +20% load makes it power-negative (the headline demo).
- Live loop: `tick_sim_s=30` every 0.5 s wall (60× real time; one orbit ≈ 95 s). `SKYTWIN_TICK_INTERVAL_S` overrides.
- Live detectors: `z=6`, `min_consecutive=2`, zero false alarms over 2000 nominal ticks (tested). Fast faults
  (load, solar, thermal spike, comms) trip residuals within 1–30 ticks; slow drifts (radiator, capacity)
  are caught later by limit checks. That's expected, not a bug.
- If you change physics parameters, re-run the What-If tests: several assert demo-relevant outcomes
  (e.g. solar −30% ⇒ CRITICAL with SAFE mode; radiator −30% ⇒ WARNING).

## Conventions

- Python 3.11+, ruff (line length 130). Pure functions and dataclasses in `twin/` and `whatif/`; I/O only in `api/` and `scripts/`.
- Frontend: React 19 + TypeScript strict + Recharts 3. Light theme: colour tokens live in `:root` in `styles.css`,
  chart colours in `lib/colors.ts` (CVD-safe order: blue, orange, aqua). Don't hard-code colours in components. Status colours are reserved for status and always ship
  with an icon or label. Every chart has a Table toggle.
- Keep API response shapes in sync with `frontend/src/types.ts`.

## Gotchas

- The repo lives in OneDrive: `npm install` is slow because OneDrive syncs `node_modules`. Pause sync or move the repo if it drags.
- The original telemanom S3 bucket returns 403; `download_nasa.py` uses the Time-Series-Library mirror on Hugging Face.
  The mirror concatenates channels in sorted `chan_id` order and SMAP excludes `P-2`; `nasa/dataset.py` relies on that.
- `backend/data/` and `frontend/dist/` are generated. Don't hand-edit them.
