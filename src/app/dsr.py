"""Data subject requests (DSRs): ingest, per-regulation deadlines, SLA status.

A DSR is a first-class ingested event. A request moves through up to three
events, all carrying the same ``extra_metadata.request_id``:

    dsr_access_request | dsr_deletion_request   the request is received
    dsr_extension                               the controller notifies an extension
    dsr_completed                               the response is sent / erasure done

Each request is stored once in ``data_subject_requests`` and its deadline is
computed from the regulation(s) of the subscriber's market.

Deadlines below are a portfolio model of the statutory response periods, not
legal advice. Where a statute sets no fixed period, ``statutory`` is False and a
documented internal policy SLA is used instead, so the dashboard never presents
a policy target as a legal deadline. Only the response deadline is modeled;
identity verification rules, exemptions and fee rules are out of scope.
"""

from __future__ import annotations

import calendar
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import DataSubjectRequest

REQUEST_EVENT_TYPES = {"dsr_access_request": "access", "dsr_deletion_request": "deletion"}
DSR_EVENT_TYPES = set(REQUEST_EVENT_TYPES) | {"dsr_extension", "dsr_completed"}

# Open requests this close to their deadline are reported as "at_risk". This is
# an operational warning window, not part of any regulation.
AT_RISK_WINDOW_DAYS = 7

# Internal SLA used when no fixed statutory period is modeled.
POLICY_SLA_DAYS = 30


@dataclass(frozen=True)
class DsrDeadline:
    regulation: str
    request_type: str  # "access" | "deletion"
    period: int
    unit: str  # "days" (calendar days) | "months" (calendar months)
    extension: int  # 0 when the statute allows no extension
    extension_unit: str
    statutory: bool  # False: no fixed statutory period, a policy SLA is applied
    citation: str
    note: str = ""

    @property
    def nominal_days(self) -> int:
        """Approximate length in days, used only when no receipt date is known."""
        return self.period * 30 if self.unit == "months" else self.period


def _gdpr(request_type: str, article: str) -> DsrDeadline:
    # GDPR Art. 12(3): respond "without undue delay and in any event within one
    # month of receipt of the request". The period "may be extended by two
    # further months where necessary", and the data subject must be told of the
    # extension, with reasons, within the first month.
    return DsrDeadline(
        "GDPR",
        request_type,
        1,
        "months",
        2,
        "months",
        True,
        f"GDPR Art. 12(3) (request under {article})",
        "One calendar month from receipt; extendable by two further months with notice inside the first month.",
    )


def _ccpa(request_type: str, right: str) -> DsrDeadline:
    # Cal. Civ. Code 1798.130(a)(2)(A): respond within 45 days of receiving a
    # verifiable consumer request; may be extended once by an additional 45
    # days when reasonably necessary, with notice within the first 45 days.
    # 11 CCR 7021 restates this in calendar days (and adds a 10 business day
    # receipt confirmation, which is not modeled here).
    return DsrDeadline(
        "CCPA",
        request_type,
        45,
        "days",
        45,
        "days",
        True,
        f"Cal. Civ. Code 1798.130(a)(2)(A); 11 CCR 7021 ({right})",
        "45 calendar days; extendable once by 45 days with notice inside the first 45 days.",
    )


DSR_DEADLINES: Dict[tuple, DsrDeadline] = {
    ("GDPR", "access"): _gdpr("access", "Art. 15"),
    ("GDPR", "deletion"): _gdpr("deletion", "Art. 17"),
    ("CCPA", "access"): _ccpa("access", "right to know, 1798.110"),
    ("CCPA", "deletion"): _ccpa("deletion", "right to delete, 1798.105"),
    # LGPD Art. 19, II: confirmation of existence of / access to personal data
    # "by means of a clear and complete declaration" within 15 days of the
    # request. The statute sets no extension.
    ("LGPD", "access"): DsrDeadline(
        "LGPD",
        "access",
        15,
        "days",
        0,
        "days",
        True,
        "LGPD Art. 19, II",
        "15 days for the complete declaration; no statutory extension.",
    ),
    # LGPD Art. 18, VI gives the right to deletion, but Art. 18 para. 5 leaves
    # the response period to ANPD regulation ("nos prazos e nos termos
    # previstos em regulamento"). We do not assert a statutory figure; the
    # 15-day access period is applied as an internal policy SLA.
    ("LGPD", "deletion"): DsrDeadline(
        "LGPD",
        "deletion",
        15,
        "days",
        0,
        "days",
        False,
        "LGPD Art. 18, VI and para. 5 (period set by ANPD regulation)",
        "No fixed period in the statute; policy SLA mirrors the 15-day access period.",
    ),
    # PIPEDA s. 8(3): respond to an access request within 30 days after
    # receipt. s. 8(4) allows an extension of up to 30 more days (or longer to
    # convert the format), with notice to the individual within the first
    # 30 days. Schedule 1, Principle 4.9 is the underlying access principle.
    ("PIPEDA", "access"): DsrDeadline(
        "PIPEDA",
        "access",
        30,
        "days",
        30,
        "days",
        True,
        "PIPEDA s. 8(3)-(4); Sch. 1 Principle 4.9",
        "30 days; extendable by up to 30 days with notice inside the first 30 days.",
    ),
    # PIPEDA has no general statutory right to erasure (Principle 4.5.3 covers
    # destroying data no longer needed; 4.9.5 covers amending inaccurate data).
    ("PIPEDA", "deletion"): DsrDeadline(
        "PIPEDA",
        "deletion",
        POLICY_SLA_DAYS,
        "days",
        0,
        "days",
        False,
        "PIPEDA Sch. 1 Principles 4.5.3, 4.9.5 (no general erasure right)",
        "No statutory erasure deadline; tracked against the internal 30-day SLA.",
    ),
    # APPI (Japan) Art. 33(2) (disclosure) and Art. 35 (cessation of use /
    # erasure) require the business to act "without delay" and set no day
    # count. Article numbers follow the Act as amended in 2020/2021 (in force
    # April 2022); verify against the PPC English translation before relying
    # on them.
    ("APPI", "access"): DsrDeadline(
        "APPI",
        "access",
        POLICY_SLA_DAYS,
        "days",
        0,
        "days",
        False,
        "APPI Art. 33(2) (without delay, no fixed period)",
        '"Without delay" in the statute; tracked against the internal 30-day SLA.',
    ),
    ("APPI", "deletion"): DsrDeadline(
        "APPI",
        "deletion",
        POLICY_SLA_DAYS,
        "days",
        0,
        "days",
        False,
        "APPI Art. 35 (without delay, no fixed period)",
        '"Without delay" in the statute; tracked against the internal 30-day SLA.',
    ),
}


def get_deadline(regulation: str, request_type: str) -> DsrDeadline:
    """Deadline rule for a regulation and request type.

    Regulations whose DSR periods have not been researched for this model fall
    back to the internal policy SLA and say so, rather than guessing a figure.
    """
    found = DSR_DEADLINES.get((regulation, request_type))
    if found:
        return found
    return DsrDeadline(
        regulation,
        request_type,
        POLICY_SLA_DAYS,
        "days",
        0,
        "days",
        False,
        "not modeled",
        f"{regulation} DSR period not modeled in this project; internal 30-day SLA applied.",
    )


def add_months(d: date, months: int) -> date:
    """Calendar-month arithmetic; clamps to the last day of a shorter month.

    GDPR periods run from the day of receipt to the same day in the following
    month (Regulation 1182/71, as applied in EDPB guidance); when that day does
    not exist the period ends on the last day of the month.
    """
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _shift(d: date, amount: int, unit: str) -> date:
    return add_months(d, amount) if unit == "months" else d + timedelta(days=amount)


def due_date(rule: DsrDeadline, received: date, extended: bool = False) -> date:
    """Last day on which a response is on time."""
    due = _shift(received, rule.period, rule.unit)
    if extended and rule.extension:
        due = _shift(due, rule.extension, rule.extension_unit)
    return due


def extension_honored(rule: DsrDeadline, received: date, noticed: Optional[date]) -> bool:
    """An extension counts only if the statute allows one and notice went out in time."""
    return bool(noticed and rule.extension and noticed <= due_date(rule, received))


def evaluate_request(
    regulations: List[str],
    request_type: str,
    received_at: datetime,
    completed_at: Optional[datetime] = None,
    extension_noticed_at: Optional[datetime] = None,
    as_of: Optional[datetime] = None,
    at_risk_days: int = AT_RISK_WINDOW_DAYS,
) -> Dict[str, Any]:
    """SLA status of one request against every regulation that applies to it.

    Status is ``on_time``, ``at_risk`` (open, within the warning window),
    ``breached`` (closed late, or open past the deadline) or ``no_rule`` (the
    market has no regulation configured). The binding rule is the one with the
    earliest due date.
    """
    as_of = as_of or datetime.utcnow()
    received = received_at.date()
    noticed = extension_noticed_at.date() if extension_noticed_at else None
    end = completed_at or as_of
    elapsed_days = round((end - received_at).total_seconds() / 86400, 1)

    if not regulations:
        return {
            "status": "no_rule",
            "state": "closed" if completed_at else "open",
            "elapsed_days": elapsed_days,
            "due": None,
            "deadline_days": None,
            "extended": False,
            "late_extension": False,
            "binding": None,
            "rules": [],
            "breached_regulations": [],
        }

    per_rule = []
    for reg in regulations:
        rule = get_deadline(reg, request_type)
        honored = extension_honored(rule, received, noticed)
        due = due_date(rule, received, extended=honored)
        per_rule.append(
            {
                "rule": rule,
                "due": due,
                "extended": honored,
                "late_extension": bool(noticed) and rule.extension > 0 and not honored,
            }
        )

    binding = min(per_rule, key=lambda r: r["due"])
    due = binding["due"]
    breached_regs = []
    for r in per_rule:
        if (completed_at and completed_at.date() > r["due"]) or (
            not completed_at and as_of.date() > r["due"]
        ):
            breached_regs.append(r["rule"].regulation)

    if breached_regs:
        status = "breached"
    elif not completed_at and (due - as_of.date()).days < at_risk_days:
        status = "at_risk"
    else:
        status = "on_time"

    return {
        "status": status,
        "state": "closed" if completed_at else "open",
        "elapsed_days": elapsed_days,
        "due": due.isoformat(),
        "deadline_days": (due - received).days,
        "extended": binding["extended"],
        "late_extension": any(r["late_extension"] for r in per_rule),
        "binding": asdict(binding["rule"]),
        "rules": [
            {
                "regulation": r["rule"].regulation,
                "due": r["due"].isoformat(),
                "statutory": r["rule"].statutory,
                "citation": r["rule"].citation,
                "extended": r["extended"],
            }
            for r in per_rule
        ],
        "breached_regulations": breached_regs,
    }


# ---------------------------------------------------------------------------
# Persistence: apply DSR events to the data_subject_requests table
# ---------------------------------------------------------------------------


def _parse(ts: Any) -> datetime:
    from .compliance_rules import _parse_timestamp

    return _parse_timestamp(ts)


def apply_dsr_event(event: Dict[str, Any], regulations: List[str], db: Session) -> Dict[str, Any]:
    """Record one DSR lifecycle event and return flags plus findings.

    Flags:
      dsr_missing_request_id     the event cannot be tied to a request
      dsr_unknown_request        extension/completion for a request never received
      dsr_late_extension         extension notice sent after the original deadline
      <reg>_data_<type>_violation  completed after the deadline for that regulation
    """
    event_type = event.get("event_type")
    extra = event.get("extra_metadata") or {}
    request_id = extra.get("request_id")
    ts = _parse(event.get("timestamp"))
    flags: List[str] = []

    if not request_id:
        return {"flags": ["dsr_missing_request_id"], "finding": None}

    row = db.query(DataSubjectRequest).filter(DataSubjectRequest.request_id == request_id).first()

    if event_type in REQUEST_EVENT_TYPES:
        if row is None:
            row = DataSubjectRequest(
                request_id=request_id,
                user_id=event.get("user_id"),
                region=event.get("region"),
                request_type=REQUEST_EVENT_TYPES[event_type],
                regulations=json.dumps(regulations),
                received_at=ts,
            )
            db.add(row)
        # A repeated receipt event for the same id is idempotent.
    elif row is None:
        return {"flags": ["dsr_unknown_request"], "finding": None}
    elif event_type == "dsr_extension":
        if row.extension_noticed_at is None:
            row.extension_noticed_at = ts
    elif event_type == "dsr_completed":
        if row.completed_at is None:
            row.completed_at = ts
    row.last_event_id = event.get("event_id")
    db.flush()

    finding = evaluate_request(
        json.loads(row.regulations or "[]"),
        row.request_type,
        row.received_at,
        row.completed_at,
        row.extension_noticed_at,
        as_of=ts,
    )
    if event_type == "dsr_extension" and finding["late_extension"]:
        flags.append("dsr_late_extension")
    if event_type == "dsr_completed":
        action = "data_access" if row.request_type == "access" else "data_deletion"
        flags.extend(f"{reg.lower()}_{action}_violation" for reg in finding["breached_regulations"])
    finding["request_id"] = request_id
    finding["request_type"] = row.request_type
    return {"flags": flags, "finding": finding}


def request_to_dict(row: DataSubjectRequest, as_of: Optional[datetime] = None) -> Dict[str, Any]:
    regs = json.loads(row.regulations or "[]")
    status = evaluate_request(
        regs, row.request_type, row.received_at, row.completed_at, row.extension_noticed_at, as_of=as_of
    )
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None  # noqa: E731
    return {
        "request_id": row.request_id,
        "user_id": row.user_id,
        "region": row.region,
        "request_type": row.request_type,
        "regulations": regs,
        "received_at": iso(row.received_at),
        "extension_noticed_at": iso(row.extension_noticed_at),
        "completed_at": iso(row.completed_at),
        **status,
    }


def list_requests(db: Session, as_of: Optional[datetime] = None) -> List[Dict[str, Any]]:
    rows = db.query(DataSubjectRequest).order_by(DataSubjectRequest.received_at.desc()).all()
    return [request_to_dict(r, as_of) for r in rows]


def summarize(requests: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {"on_time": 0, "at_risk": 0, "breached": 0, "no_rule": 0}
    by_regulation: Dict[str, Dict[str, int]] = {}
    for r in requests:
        by_status[r["status"]] += 1
        for reg in r["regulations"] or ["none"]:
            bucket = by_regulation.setdefault(reg, {k: 0 for k in by_status})
            bucket[r["status"]] += 1
    return {"total": len(requests), "by_status": by_status, "by_regulation": by_regulation}


def deadline_table() -> List[Dict[str, Any]]:
    """Every modeled rule, for docs, the API and the demo."""
    return [asdict(rule) for rule in DSR_DEADLINES.values()]
