"""SkyTwin HTTP/WebSocket API.

There is deliberately no endpoint that commands the spacecraft. What-If runs on snapshots; the only
write access to the live model is the demo fault-injection endpoint, which emulates real-world events.
"""

import asyncio
import contextlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from ..config import LIMITS
from ..telemetry.live import LiveTwin
from ..whatif import catalog, simulate
from .schemas import CompareRequest, PerturbationIn, SimulateRequest

BACKEND_DIR = Path(__file__).resolve().parents[2]
VALIDATION_REPORT = BACKEND_DIR / "data" / "validation_report.json"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


class Hub:
    """Fan-out of live telemetry to connected WebSocket clients."""

    def __init__(self) -> None:
        self.queues: set[asyncio.Queue] = set()

    def publish(self, message: dict) -> None:
        for q in list(self.queues):
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            q.put_nowait(message)


async def _live_loop(app: FastAPI, interval_s: float) -> None:
    while True:
        app.state.hub.publish(app.state.live.tick())
        await asyncio.sleep(interval_s)


def create_app(start_loop: bool = True, tick_interval_s: float | None = None) -> FastAPI:
    interval = tick_interval_s if tick_interval_s is not None else float(os.getenv("SKYTWIN_TICK_INTERVAL_S", "0.5"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.live = LiveTwin()
        app.state.hub = Hub()
        task = asyncio.create_task(_live_loop(app, interval)) if start_loop else None
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="SkyTwin", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/config")
    async def config():
        live: LiveTwin = app.state.live
        p = live.params
        return {
            "limits": [limit.__dict__ for limit in LIMITS],
            "orbit_period_min": p.orbit_period_s / 60.0,
            "tick_sim_s": live.tick_sim_s,
            "tick_interval_s": interval,
            "battery_capacity_wh": p.battery_capacity_wh,
            "solar_array_peak_w": p.solar_array_peak_w,
        }

    @app.get("/api/twin/state")
    async def twin_state():
        live: LiveTwin = app.state.live
        return live.latest or live.tick()

    @app.get("/api/twin/history")
    async def twin_history():
        return list(app.state.live.history)

    @app.get("/api/live/alerts")
    async def alerts():
        return list(app.state.live.alerts)

    @app.get("/api/live/faults")
    async def faults():
        return app.state.live.faults

    @app.post("/api/live/faults", status_code=201)
    async def inject_fault(body: PerturbationIn):
        app.state.live.inject_fault(body.to_domain())
        return app.state.live.faults

    @app.delete("/api/live/faults")
    async def clear_faults():
        app.state.live.clear_faults()
        return []

    @app.get("/api/scenarios")
    async def scenarios():
        return catalog()

    async def _simulate(req: SimulateRequest, snapshot) -> dict:
        perturbations = [p.to_domain() for p in req.perturbations]
        try:
            return await run_in_threadpool(simulate, snapshot, perturbations, req.horizon_min, app.state.live.params, req.label)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/simulate")
    async def run_simulation(req: SimulateRequest):
        # Snapshot on the event-loop thread so it can't interleave with a live tick.
        return await _simulate(req, app.state.live.snapshot())

    @app.post("/api/compare")
    async def compare(req: CompareRequest):
        snapshot = app.state.live.snapshot()
        a, b = await asyncio.gather(_simulate(req.a, snapshot), _simulate(req.b, snapshot))
        return {"a": a, "b": b}

    @app.get("/api/validation")
    async def validation():
        if not VALIDATION_REPORT.exists():
            return {"available": False}
        report = json.loads(VALIDATION_REPORT.read_text(encoding="utf-8"))
        for method in report.get("methods", []):
            method.pop("sweep", None)
        return {"available": True, **report}

    @app.websocket("/ws/telemetry")
    async def telemetry(ws: WebSocket):
        await ws.accept()
        queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        app.state.hub.queues.add(queue)
        try:
            await ws.send_json({"type": "history", "frames": list(app.state.live.history), "alerts": list(app.state.live.alerts)})
            while True:
                await ws.send_json(await queue.get())
        except WebSocketDisconnect:
            pass
        finally:
            app.state.hub.queues.discard(queue)

    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app


app = create_app()
