"""Limit-crossing analysis over predicted trajectories."""

from dataclasses import dataclass

from ..config import LIMITS, Limit

SEVERITY_RANK = {None: 0, "warning": 1, "critical": 2}
RISK_LEVELS = ("NOMINAL", "CAUTION", "WARNING", "CRITICAL")


@dataclass(frozen=True)
class Crossing:
    severity: str
    first_min: float
    limit: float
    extreme: float


def _threshold(limit: Limit, bound: str, severity: str) -> float | None:
    return getattr(limit, f"{'crit' if severity == 'critical' else 'warn'}_{bound}")


def worst_crossing(points: list[dict], limit: Limit, bound: str) -> Crossing | None:
    """Worst severity reached on one side of a limit, with the first time that severity was reached."""
    values = [p[limit.channel] for p in points]
    extreme = min(values) if bound == "low" else max(values)
    for severity in ("critical", "warning"):
        threshold = _threshold(limit, bound, severity)
        if threshold is None:
            continue
        for p, v in zip(points, values):
            if (v < threshold) if bound == "low" else (v > threshold):
                return Crossing(severity, p["t_min"], threshold, extreme)
    return None


def safe_mode_entry(points: list[dict]) -> tuple[float, str | None] | None:
    for p in points:
        if p["mode"] == "SAFE":
            return p["t_min"], p.get("safe_mode_reason")
    return None


def _finding(limit: Limit, bound: str, c: Crossing, confidence: str, pre_existing: bool) -> dict:
    return {
        "channel": limit.channel,
        "label": limit.label,
        "unit": limit.unit,
        "bound": bound,
        "severity": c.severity,
        "limit": c.limit,
        "first_crossing_min": c.first_min,
        "extreme": c.extreme,
        "confidence": confidence,
        "pre_existing": pre_existing,
    }


def analyze(baseline: list[dict], scenario: list[dict], members: list[list[dict]]) -> list[dict]:
    """Findings for the nominal scenario ("likely") plus worse outcomes seen only in the ensemble ("possible")."""
    findings = []
    for limit in LIMITS:
        for bound in ("low", "high"):
            if _threshold(limit, bound, "warning") is None and _threshold(limit, bound, "critical") is None:
                continue
            nominal = worst_crossing(scenario, limit, bound)
            base = worst_crossing(baseline, limit, bound)
            if nominal:
                pre = base is not None and SEVERITY_RANK[base.severity] >= SEVERITY_RANK[nominal.severity]
                findings.append(_finding(limit, bound, nominal, "likely", pre))
            worst_member = None
            for member in members:
                c = worst_crossing(member, limit, bound)
                if c and (
                    worst_member is None
                    or SEVERITY_RANK[c.severity] > SEVERITY_RANK[worst_member.severity]
                    or (c.severity == worst_member.severity and c.first_min < worst_member.first_min)
                ):
                    worst_member = c
            if worst_member and SEVERITY_RANK[worst_member.severity] > SEVERITY_RANK[nominal.severity if nominal else None]:
                findings.append(_finding(limit, bound, worst_member, "possible", False))

    safe = safe_mode_entry(scenario)
    base_safe = safe_mode_entry(baseline)
    if safe:
        findings.append(_safe_mode_finding(safe, "likely", base_safe is not None))
    else:
        member_entries = [e for e in (safe_mode_entry(m) for m in members) if e]
        if member_entries:
            findings.append(_safe_mode_finding(min(member_entries), "possible", False))

    findings.sort(key=lambda f: (f["confidence"] != "likely", -SEVERITY_RANK[f["severity"]], f["first_crossing_min"]))
    return findings


def _safe_mode_finding(entry: tuple[float, str | None], confidence: str, pre_existing: bool) -> dict:
    t_min, reason = entry
    return {
        "channel": "mode",
        "label": "Onboard SAFE mode",
        "unit": "",
        "bound": "state",
        "severity": "critical",
        "limit": None,
        "first_crossing_min": t_min,
        "extreme": None,
        "reason": reason,
        "confidence": confidence,
        "pre_existing": pre_existing,
    }


def risk_level(findings: list[dict]) -> str:
    likely = [f["severity"] for f in findings if f["confidence"] == "likely"]
    if "critical" in likely:
        return "CRITICAL"
    if "warning" in likely:
        return "WARNING"
    if findings:
        return "CAUTION"
    return "NOMINAL"
