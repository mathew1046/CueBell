import time
import uuid
from collections import deque

from .models import EventObservation, Intent, MonitoringTask, ProposedEvent, Segment
from .validation import validate_event, validate_match


def identity(item: dict) -> tuple:
    if item.get("monitor_id"):
        return ("event", item["monitor_id"], item.get("location"))
    return ("queue", item.get("token_normalized", item.get("token")), item.get("counter"))


def positive(item: dict) -> bool:
    return item["type"] in {"CALL", "CORRECT", "REPEAT", "MATCH"} and (
        not item.get("monitor_id") or item.get("condition_met") is True
    )


class Engine:
    """One ordered in-memory monitor. No async mutation happens inside this reducer."""

    def __init__(self, grace: float = 1.2):
        self.grace = grace
        self.rule: dict | None = None
        self.history: deque[dict] = deque(maxlen=100)
        self.observations: deque[dict] = deque(maxlen=50)
        self.alerts: deque[dict] = deque(maxlen=20)
        self.pending: list[tuple[float, dict]] = []
        self.sequence = 0
        self.generation = 0
        self.seen: deque[tuple] = deque(maxlen=200)
        # Private aliases connect suppressed duplicates/repeats to their original call.
        self._occurrences: dict[str, str] = {}

    def emit(self, kind: str, **payload) -> dict:
        self.sequence += 1
        event = {"type": kind, "sequence": self.sequence, "at": time.time(), **payload}
        self.history.append(event)
        return event

    def activate(self, intent: Intent) -> dict:
        self.generation += 1
        # Confirmation starts a fresh monitor; old session snapshots must not replay
        # cleared transcripts or alerts after an offline local stop and restart.
        self.history.clear()
        self.pending.clear()
        self.observations.clear()
        self._occurrences.clear()
        self.alerts.clear()
        self.seen.clear()
        self.rule = {
            "id": uuid.uuid4().hex,
            "intent": intent.intent,
            "context": intent.context,
            "token": intent.token,
            "alert_preferences": sorted(set(intent.alert_preferences) | {"visual"}),
            "status": "ACTIVE",
            "created_at": time.time(),
        }
        if intent.task:
            self.rule["task"] = intent.task.model_dump()
        return self.emit("monitor.created", rule=self.rule.copy())

    def control(self, action: str, alert_id: str | None = None) -> dict:
        if action == "acknowledge":
            alert = next((a for a in self.alerts if a["id"] == alert_id), None)
            if not alert:
                raise ValueError("Alert is no longer available.")
            alert["acknowledged"] = True
            if alert["state"] != "corrected":
                alert["state"] = "acknowledged"
            return self.emit("alert.acknowledged", alert=alert.copy())
        if not self.rule:
            raise ValueError("No confirmed monitor.")
        if self.rule["status"] == "STOPPED" and action != "stop":
            raise ValueError(
                "Submit and confirm a new request before restarting a stopped monitor."
            )
        self.generation += 1
        self.pending.clear()
        self.observations.clear()
        self._occurrences.clear()
        self.rule["status"] = {"pause": "PAUSED", "resume": "ACTIVE", "stop": "STOPPED"}[action]
        return self.emit(f"monitor.{action}", rule=self.rule.copy())

    def gap(self) -> None:
        # Old pending matches must not become current-looking alerts after reconnection.
        self.pending.clear()
        self.observations.clear()
        self._occurrences.clear()
        self.generation += 1

    def recent_observations(self, now: float) -> list[dict]:
        """Correction context only: no rule, preferences, alert/match state, or stale coverage."""
        keys = (
            "id",
            "type",
            "token_normalized",
            "counter",
            "evidence_text",
            "source_segment_ids",
            "summary",
            "location",
            "identifiers",
            "condition_met",
        )
        return [
            {key: observation[key] for key in keys if key in observation}
            for observation in list(self.observations)[-8:]
            if observation["state"] == "confirmed"
            and observation["type"] in {"CALL", "CORRECT", "REPEAT", "MATCH"}
            and 0 <= now - observation["at"] <= 30
        ]

    def ingest(self, proposed: ProposedEvent, window: list[Segment], now: float) -> list[dict]:
        return self._ingest(validate_event(proposed, window).model_dump(), now)

    def ingest_match(
        self, proposed: EventObservation, window: list[Segment], now: float
    ) -> list[dict]:
        if not self.rule or not self.rule.get("task") or self.rule["status"] != "ACTIVE":
            return []
        event = validate_match(proposed, window, MonitoringTask.model_validate(self.rule["task"]))
        return self._ingest({**event.model_dump(), "monitor_id": self.rule["id"]}, now)

    def _ingest(self, event: dict, now: float) -> list[dict]:
        key = (
            event["type"],
            identity(event),
            event.get("condition_met"),
            tuple(event["source_segment_ids"]),
            event["replaces_event_id"],
        )
        if key in self.seen:
            return []
        self.seen.append(key)
        observation = {
            **event,
            "id": uuid.uuid4().hex,
            "at": now,
            "state": "uncertain" if event["type"] == "UNCERTAIN" else "confirmed",
        }
        outputs = []
        if event["type"] == "UNCERTAIN":
            # An unresolved correction must not release an earlier, now-doubtful call.
            # Conservatively withhold all pending calls rather than guess its target.
            self.pending.clear()
        if event["type"] in {"CORRECT", "CANCEL"}:
            old = next(
                (
                    o
                    for o in self.observations
                    if o["id"] == event["replaces_event_id"]
                    and o["state"] == "confirmed"
                    and o["type"] in {"CALL", "CORRECT", "REPEAT", "MATCH"}
                    and 0 <= now - o["at"] <= 30
                    and (
                        event["type"] != "CANCEL"
                        or (event.get("monitor_id") and event["monitor_id"] == o.get("monitor_id"))
                        or (
                            event.get("token_normalized") == o.get("token_normalized")
                            and not event.get("monitor_id")
                            and not o.get("monitor_id")
                            and (
                                event.get("counter") is None
                                or o.get("counter") is None
                                or event.get("counter") == o.get("counter")
                            )
                        )
                    )
                ),
                None,
            )
            if old is None:
                self.pending.clear()
                observation.update(
                    type="UNCERTAIN",
                    state="uncertain",
                    ambiguity_reason="Correction target cannot be resolved.",
                )
            else:
                occurrence = self._occurrences.get(old["id"], old["id"])
                affected = {occurrence} | {
                    oid for oid, original in self._occurrences.items() if original == occurrence
                }
                for prior in self.observations:
                    if prior["id"] in affected:
                        prior["state"] = "cancelled" if event["type"] == "CANCEL" else "superseded"
                self.pending = [(due, o) for due, o in self.pending if o["id"] not in affected]
                for alert in self.alerts:
                    if alert["observation_id"] in affected and alert["state"] != "corrected":
                        alert["state"] = "corrected"
                        alert["acknowledged"] = False
                        outputs.append(
                            self.emit(
                                "alert.corrected", alert=alert.copy(), correction=observation.copy()
                            )
                        )
        occurrence = observation["id"]
        if observation["state"] == "confirmed" and positive(observation):
            # Reuse only an original within the same 45-second alert-dedup window;
            # a chain of repeats must not merge a genuinely later call forever.
            candidates = (
                [
                    (a["observation_id"], identity(a), a["observed_at"])
                    for a in self.alerts
                    if a["state"] != "corrected"
                ]
                + [(o["id"], identity(o), o["at"]) for _, o in self.pending]
                + [
                    (o["id"], identity(o), o["at"])
                    for o in self.observations
                    if o["state"] == "confirmed"
                    and positive(o)
                    and self._occurrences.get(o["id"], o["id"]) == o["id"]
                ]
            )
            for oid, event_identity, at in candidates:
                if event_identity == identity(observation) and 0 <= now - at < 45:
                    occurrence = oid
                    break
        self.observations.append(observation)
        retained = {o["id"] for o in self.observations}
        self._occurrences = {
            oid: original for oid, original in self._occurrences.items() if oid in retained
        }
        self._occurrences[observation["id"]] = occurrence
        outputs.append(self.emit("observation", observation=observation.copy()))
        if (
            self.rule
            and self.rule["status"] == "ACTIVE"
            and observation["type"] in {"CALL", "CORRECT", "MATCH"}
            and positive(observation)
            and (
                observation.get("monitor_id") == self.rule["id"]
                if self.rule.get("task")
                else observation.get("token_normalized") == self.rule["token"]
            )
        ):
            duplicate = any(
                identity(a) == identity(observation)
                and a["state"] != "corrected"
                and now - a["observed_at"] < 45
                for a in self.alerts
            )
            pending_duplicate = any(identity(o) == identity(observation) for _, o in self.pending)
            if not duplicate and not pending_duplicate:
                self.pending.append((now + self.grace, observation))
        return outputs

    def next_pending_due(self) -> float | None:
        return min((due for due, _ in self.pending), default=None)

    def flush(self, now: float) -> list[dict]:
        ready = [o for due, o in self.pending if due <= now]
        self.pending = [(due, o) for due, o in self.pending if due > now]
        results = []
        for observation in ready:
            if not self.rule or self.rule["status"] != "ACTIVE":
                continue
            if observation["state"] != "confirmed":
                continue
            if not 0 <= now - observation["at"] <= 15:
                continue  # Never dress an overdue pending call up as a real-time alert.
            alert = {
                "id": uuid.uuid4().hex,
                "observation_id": observation["id"],
                "token": observation.get("token_normalized"),
                "counter": observation.get("counter"),
                "observed_at": observation["at"],
                "state": "unacknowledged",
                "acknowledged": False,
                "alert_preferences": self.rule["alert_preferences"],
            }
            if observation.get("monitor_id"):
                alert.update(
                    monitor_id=observation["monitor_id"],
                    summary=observation["summary"],
                    location=observation["location"],
                    evidence_text=observation["evidence_text"],
                    task_summary=self.rule["task"]["summary"],
                )
            self.alerts.append(alert)
            results.append(self.emit("alert", alert=alert.copy()))
        return results
