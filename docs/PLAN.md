# SkyTwin — Implementation Plan

Spacecraft digital twin with two modes:

- **Live Mode** — what is happening right now? Telemetry → twin → current state → anomaly detection.
- **Simulation Mode (What-If Engine)** — what would happen if…? Operator picks a scenario → the twin
  propagates it forward in a sandbox → predicted state, risks, and a plain-English explanation.

> "SkyTwin doesn't only tell the operator what is happening; it lets them safely explore what could
> happen before taking an action." Simulate → Evaluate → Operator decides → real command (outside SkyTwin).

Constraints: 18-hour hackathon, team of 2–4, Python (FastAPI) + React (TypeScript), subsystems
**Power + Battery + Thermal** (+ a lightweight comms/data-storage model for the comm-loss scenario).

---

## 1. Architecture

```
                 ┌───────────────────────── backend (FastAPI) ─────────────────────────┐
                 │                                                                     │
 NASA SMAP/MSL ─▶│ nasa/  (offline)  ──▶ validation_report.json ──▶ GET /api/validation │
                 │                                                                     │
                 │ twin/  ← shared physics: orbit · power · battery · thermal · data   │
                 │   ▲                       ▲                                         │
                 │   │ "truth" spacecraft    │ sandboxed copies (never the live one)   │
                 │ telemetry/live.py       whatif/engine.py                            │
                 │   noise + faults          baseline vs scenario + ensemble band      │
                 │   residual detector       risk.py · narrative.py                    │
                 │   limit checks                                                      │
                 │   │                        ▲                                        │
                 └───┼────────────────────────┼────────────────────────────────────────┘
                     │ WS /ws/telemetry       │ POST /api/simulate · /api/compare
                 ┌───▼────────────────────────┴───────────── frontend (React) ─────────┐
                 │  Live Mode (green)                     Simulation Mode (blue)        │
                 └─────────────────────────────────────────────────────────────────────┘
```

**Key design decisions**

| Decision | Why |
|---|---|
| One physics core (`twin/`) drives both modes | What-If predictions use exactly the model that tracks the live spacecraft — no separate "mock" to drift out of sync. |
| What-If engine only ever works on a **deep-copied snapshot** | Sandbox is structural, not a convention. A test asserts live state is unchanged after simulation. There is no command endpoint. |
| Live anomaly detection = **twin residuals** + **limit checks** | Residual = measured − what the nominal twin predicted one tick ahead. That is the real digital-twin idea: flag behaviour the physics can't explain (e.g. solar array output 30 % low). Limit checks flag out-of-range values. |
| NASA SMAP/MSL used to **validate the detector**, not to calibrate physics | The public dataset is normalised and channel names are anonymised, so it can't give physical ranges — but it has real labelled spacecraft anomalies, so it's the right benchmark for the dynamic-threshold scoring algorithm. Tuned on SMAP, reported on MSL (held out). |
| Baseline vs scenario from the same snapshot | "Impact" is always a difference against doing nothing, so orbit-driven swings aren't mistaken for scenario effects. |
| Small ensemble (magnitude ±10 %, environment ±5 %) | Gives an honest uncertainty band and a "possible" risk tier without heavy statistics. |

---

## 2. Physics model (MVP)

LEO small-sat, 95-min orbit, 35 % eclipse. Explicit Euler, 10 s step.

- **Orbit**: sunlit/eclipse from orbit phase, 60 s penumbra ramp.
- **Power**: solar = peak × sun factor × degradation; loads = bus + payload + comms (TX or RX-only) + heater.
- **Battery**: SOC integrates net power (charge efficiency 0.95), OCV(SOC), IR drop, I²R heat.
- **Thermal**: two lumped nodes (bus, battery). Bus: absorbed solar + load dissipation − radiation (Stefan–Boltzmann).
  Battery: conduction from bus + I²R + heater. Heater thermostat with hysteresis.
- **Data**: payload generates data, link downlinks it; blackout → backlog → recovery time.
- **FDIR**: onboard autonomy latches **SAFE mode** (payload off) on SOC < 25 % or battery > 45 °C.

## 3. Scenarios (What-If)

| Kind | Parameter | Effect |
|---|---|---|
| `load_increase` | % | All non-heater loads × (1 + %) |
| `solar_degradation` | % | Solar output × (1 − %) |
| `battery_capacity_loss` | % | Usable capacity × (1 − %) |
| `thermal_spike` | °C | Instant temperature rise on bus + battery |
| `radiator_degradation` | % | Radiator emissivity × (1 − %) |
| `comms_blackout` | duration | Link down; TX idles; data accumulates |
| `payload_off` | — | Mitigation: payload powered down |

Each perturbation has `start_min` and optional `duration_min` (omitted = persistent). Scenarios are lists,
so compound cases ("+20 % load **and** payload shed") work, and `/api/compare` runs two from one snapshot.

**Outputs**: baseline + predicted trajectories, uncertainty band, impact chain (↑/↓ with values), risk
findings with first-crossing time (likely/possible), risk level (NOMINAL · CAUTION · WARNING · CRITICAL),
endurance (time to SOC critical), recovery time, narrative, recommendations.

---

## 4. Build phases (18 h, team of 2–4)

Lanes: **A** twin core + What-If · **B** backend API + live loop · **C** Live UI · **D** Simulation UI + NASA validation.
With 2 people: A+B and C+D. Every phase ends with a check that must pass before moving on.

| Hours | A — twin + engine | B — API + live | C — Live UI | D — Sim UI + NASA |
|---|---|---|---|---|
| 0–1 | Repo scaffold, dev guide, venv, `npm install` — **everyone** | | | Start dataset download |
| 1–4 | `twin/` subsystems + `Spacecraft`; unit tests | Live loop stub on fake frames; WS hub | Layout, mode tabs, stat tiles on mock data | Dataset loader + labels parser + tests |
| 4–7 | `whatif/engine` baseline/scenario/ensemble; risk | Wire real `LiveTwin`; REST endpoints | Live charts from WS | Detector + scoring + validation script |
| 7–10 | Narrative, impacts, endurance/recovery | `/simulate`, `/compare`, faults API; API tests | Alerts panel, fault-injection panel | Scenario builder, results charts |
| 10–14 | Tune parameters so demo scenarios read well | Static serving of built UI; hardening | Validation badge; polish | Compare view, impact chain, narrative |
| 14–16 | Fix bugs from integration | End-to-end smoke test | Browser pass on both modes | Browser pass; demo presets |
| 16–18 | **Freeze features.** Rehearse the demo script twice, fix only demo-blocking bugs, record a backup video. | | | |

**Checks per phase**: `pytest` green (phase 1–2), `curl /api/simulate` returns a sane result (phase 3),
both modes work in the browser (phase 4), full demo script runs start-to-finish without touching code (phase 5).

**Cut list if behind** (cut in this order): scenario comparison → ensemble band → NASA validation badge
(keep the script) → radiator/battery-loss scenarios → static serving.

---

## 5. Demo script (≈4 min)

1. **Live Mode** — orbit clock ticking, sunlight/eclipse, SOC charging/discharging. "This is the twin tracking the spacecraft."
2. Show validation badge: "the anomaly-scoring algorithm is benchmarked against real labelled NASA SMAP/MSL anomalies."
3. Inject **solar array damage 30 %** (demo event) → residual anomaly fires on solar power within seconds, before any limit is crossed. "The twin noticed the physics stopped matching."
4. Switch to **Simulation Mode** (colour changes). Run **"Power consumption +20 %"** → impact chain, SOC trend, endurance estimate, narrative.
5. **Compare** with "+20 % with payload shed" → mitigation shown side by side.
6. Run **"Comms blackout 10 min"** → data backlog + recovery time. Run **"Temperature +15 °C"** → thermal recovery.
7. Point at the disabled **Send to spacecraft** button: simulate → evaluate → operator decides.

---

## 6. Beyond the brief (added ideas)

- **Residual-based detection** — catches faults before limits trip (the strongest "why a twin?" argument).
- **Onboard FDIR / SAFE mode** in the model — What-If shows *when* autonomy would take over and what mission is lost.
- **Endurance & recovery metrics** — "SOC critical in 9.4 h", "backlog clears 6 min after link returns".
- **Impact chain** mirroring the operator's mental model (load ↑ → discharge ↑ → temp ↑ → SOC ↓ → endurance ↓).
- **Scenario comparison** from one snapshot, for mitigation trade-offs.
- **Uncertainty band + "possible" risk tier** from a 4-member ensemble.
- **Disabled "Send to spacecraft"** control that makes the sandbox boundary visible.
- **Held-out validation** (tune on SMAP, report on MSL) so the NASA number is honest.

## 7. Trained LSTM detector (added)

`training/SkyTwin_LSTM_Training.ipynb` trains a 2×64 LSTM next-value predictor on the unlabelled SMAP/MSL
train splits on Colab (Run all, unattended, checkpoints to Drive) and exports ONNX. Drop the two files into
`backend/models/` and re-run `validate_anomalies.py`: the benchmark card then compares statistical vs LSTM
on held-out MSL.

Finding: a 1-step predictor copies the latest value and tracks anomalies (MSL F1 0.42, below the
statistical 0.44). Predicting 30 steps ahead fixed it: SMAP F1 0.67 (used for selection), held-out MSL F1 0.59.
The notebook now defaults to `--horizon 30`.

## 8. Future work (post-hackathon)

Real telemetry ingest (CCSDS/MQTT), state estimation (Kalman filter) instead of full-state observation,
LSTM predictor for the NASA benchmark (Telemanom-style), attitude/ADCS subsystem, ground-station pass
scheduling, scenario history persistence, multi-operator auth.
