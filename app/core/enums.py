from __future__ import annotations

from enum import Enum


class Protocol(str, Enum):
    RTSP = "rtsp"
    HTTP = "http"
    HTTPS = "https"


class CameraHealth(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPED = "stopped"


class DecisionState(str, Enum):
    COMPLIANT = "compliant"
    SUSPECTED_NON_COMPLIANCE = "suspected_non_compliance"
    CONFIRMED_NON_COMPLIANCE = "confirmed_non_compliance"
    DISCARDED_DUE_TO_UNCERTAINTY = "discarded_due_to_uncertainty"


class ReportKind(str, Enum):
    EVENT = "event"
    DAILY = "daily"


class ReportStatus(str, Enum):
    PENDING = "pending"
    GENERATED = "generated"
    FAILED = "failed"


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
