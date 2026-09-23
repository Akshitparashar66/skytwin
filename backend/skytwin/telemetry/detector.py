"""Dynamic-threshold residual detector.

Scores a stream of residuals (actual − predicted): the score is an exponentially smoothed residual,
and a point is anomalous when the score exceeds mean + z·std of recent *nominal* scores. Anomalous
scores are not learned into the statistics, so a persistent fault stays flagged.

Used in Live Mode on twin residuals, and benchmarked offline on NASA SMAP/MSL telemetry.
"""

import math
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    score: float
    threshold: float
    is_anomaly: bool
    smoothed: float = 0.0


class DynamicThresholdDetector:
    def __init__(
        self,
        alpha: float = 0.2,
        window: int = 250,
        z: float = 5.0,
        min_std: float = 1e-6,
        warmup: int = 30,
        signed: bool = True,
        min_consecutive: int = 1,
    ):
        self.alpha = alpha
        self.z = z
        self.min_std = min_std
        self.warmup = warmup
        self.signed = signed
        self.min_consecutive = min_consecutive
        self._smoothed = 0.0
        self._scores: deque[float] = deque(maxlen=window)
        self._sum = 0.0
        self._sum_sq = 0.0
        self._streak = 0

    def _learn(self, score: float) -> None:
        if len(self._scores) == self._scores.maxlen:
            old = self._scores[0]
            self._sum -= old
            self._sum_sq -= old * old
        self._scores.append(score)
        self._sum += score
        self._sum_sq += score * score

    def threshold(self) -> float:
        n = len(self._scores)
        if n == 0:
            return math.inf
        mean = self._sum / n
        var = max(self._sum_sq / n - mean * mean, 0.0)
        return mean + self.z * max(math.sqrt(var), self.min_std)

    def update(self, residual: float) -> Detection:
        value = residual if self.signed else abs(residual)
        self._smoothed = self.alpha * value + (1.0 - self.alpha) * self._smoothed
        score = abs(self._smoothed)
        threshold = self.threshold()
        exceeded = len(self._scores) >= self.warmup and score > threshold
        self._streak = self._streak + 1 if exceeded else 0
        if not exceeded:
            self._learn(score)
        return Detection(score, threshold, self._streak >= self.min_consecutive, self._smoothed)
