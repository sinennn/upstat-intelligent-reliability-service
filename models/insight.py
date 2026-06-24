from dataclasses import dataclass


@dataclass(frozen=True)
class Insight:
    monitor_id: str
    monitor_name: str
    risk_score: int
    anomaly_detected: bool
    severity: str
    summary: str
    recommended_action: str
    human_readable: str | None = None

    def to_dict(self) -> dict:
        return {
            "monitor_id": self.monitor_id,
            "monitor_name": self.monitor_name, 
            "risk_score": int(self.risk_score),
            "anomaly_detected": bool(self.anomaly_detected),
            "severity": self.severity,
            "summary": self.summary,
            "recommended_action": self.recommended_action,
            "human_readable": self.human_readable,
        }

