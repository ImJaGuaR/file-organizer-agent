from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


ActionKind = Literal["move", "skip", "delete"]
PlanMode = Literal["preview", "apply"]
RiskLevel = Literal["low", "medium", "high"]
MemorySource = Literal["user_correction", "explicit_user_request"]


class PlanValidationError(ValueError):
    """Raised when an AI-generated plan is malformed or unsafe."""


@dataclass(frozen=True)
class FileMetadata:
    path: str
    relative_path: str
    name: str
    extension: str
    size_bytes: int
    modified_at: str
    mime_type: str | None
    safe_type_guess: str
    is_hidden: bool
    is_directory: bool
    is_symlink: bool
    risk_flags: list[str] = field(default_factory=list)
    preview: str = ""
    preview_warnings: list[str] = field(default_factory=list)

    def to_model_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data["preview"]:
            data.pop("preview")
        if not data["preview_warnings"]:
            data.pop("preview_warnings")
        return data


@dataclass
class PlanAction:
    id: int
    action: ActionKind
    source_path: str
    destination_path: str | None
    confidence: float
    reasoning: str
    evidence: list[str]
    risk_level: RiskLevel
    needs_user_confirmation: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanAction":
        required = {
            "id",
            "action",
            "source_path",
            "destination_path",
            "confidence",
            "reasoning",
            "evidence",
            "risk_level",
            "needs_user_confirmation",
        }
        missing = required - data.keys()
        if missing:
            raise PlanValidationError(f"Plan action missing fields: {sorted(missing)}")
        action = data["action"]
        if action not in {"move", "skip", "delete"}:
            raise PlanValidationError(f"Invalid action: {action}")
        risk = data["risk_level"]
        if risk not in {"low", "medium", "high"}:
            raise PlanValidationError(f"Invalid risk level: {risk}")
        confidence = float(data["confidence"])
        if confidence < 0 or confidence > 1:
            raise PlanValidationError("Action confidence must be between 0 and 1")
        evidence = data["evidence"]
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise PlanValidationError("Action evidence must be a list of strings")
        return cls(
            id=int(data["id"]),
            action=action,
            source_path=str(data["source_path"]),
            destination_path=None if data["destination_path"] is None else str(data["destination_path"]),
            confidence=confidence,
            reasoning=str(data["reasoning"]),
            evidence=evidence,
            risk_level=risk,
            needs_user_confirmation=bool(data["needs_user_confirmation"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrganizationPlan:
    request_summary: str
    source_root: str
    destination_root: str
    mode: PlanMode
    requires_approval: bool
    global_reasoning: str
    actions: list[PlanAction]
    questions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrganizationPlan":
        required = {
            "request_summary",
            "source_root",
            "destination_root",
            "mode",
            "requires_approval",
            "global_reasoning",
            "actions",
        }
        missing = required - data.keys()
        if missing:
            raise PlanValidationError(f"Plan missing fields: {sorted(missing)}")
        if data["mode"] not in {"preview", "apply"}:
            raise PlanValidationError("Plan mode must be preview or apply")
        actions_data = data["actions"]
        if not isinstance(actions_data, list):
            raise PlanValidationError("Plan actions must be a list")
        actions = [PlanAction.from_dict(item) for item in actions_data]
        questions = data.get("questions", [])
        warnings = data.get("warnings", [])
        if not isinstance(questions, list) or not all(isinstance(item, str) for item in questions):
            raise PlanValidationError("Plan questions must be a list of strings")
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise PlanValidationError("Plan warnings must be a list of strings")
        return cls(
            request_summary=str(data["request_summary"]),
            source_root=str(data["source_root"]),
            destination_root=str(data["destination_root"]),
            mode=data["mode"],
            requires_approval=bool(data["requires_approval"]),
            global_reasoning=str(data["global_reasoning"]),
            actions=actions,
            questions=questions,
            warnings=warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["actions"] = [action.to_dict() for action in self.actions]
        return data


@dataclass
class ValidatedAction:
    id: int
    action: ActionKind
    source_path: Path
    destination_path: Path | None
    confidence: float
    reasoning: str
    evidence: list[str]
    risk_level: RiskLevel
    needs_user_confirmation: bool


@dataclass
class ValidatedPlan:
    request_summary: str
    source_root: Path
    destination_root: Path
    mode: PlanMode
    requires_approval: bool
    global_reasoning: str
    actions: list[ValidatedAction]
    questions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_plan(self) -> OrganizationPlan:
        return OrganizationPlan(
            request_summary=self.request_summary,
            source_root=str(self.source_root),
            destination_root=str(self.destination_root),
            mode=self.mode,
            requires_approval=self.requires_approval,
            global_reasoning=self.global_reasoning,
            actions=[
                PlanAction(
                    id=action.id,
                    action=action.action,
                    source_path=str(action.source_path),
                    destination_path=str(action.destination_path) if action.destination_path else None,
                    confidence=action.confidence,
                    reasoning=action.reasoning,
                    evidence=action.evidence,
                    risk_level=action.risk_level,
                    needs_user_confirmation=action.needs_user_confirmation,
                )
                for action in self.actions
            ],
            questions=self.questions,
            warnings=self.warnings,
        )


@dataclass(frozen=True)
class MemoryItem:
    id: str
    created_at: str
    text: str
    source: MemorySource
    active: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryItem":
        return cls(
            id=str(data["id"]),
            created_at=str(data["created_at"]),
            text=str(data["text"]),
            source=data.get("source", "explicit_user_request"),
            active=bool(data.get("active", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_summary",
        "source_root",
        "destination_root",
        "mode",
        "requires_approval",
        "global_reasoning",
        "actions",
        "questions",
        "warnings",
    ],
    "properties": {
        "request_summary": {"type": "string"},
        "source_root": {"type": "string"},
        "destination_root": {"type": "string"},
        "mode": {"type": "string", "enum": ["preview", "apply"]},
        "requires_approval": {"type": "boolean"},
        "global_reasoning": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "action",
                    "source_path",
                    "destination_path",
                    "confidence",
                    "reasoning",
                    "evidence",
                    "risk_level",
                    "needs_user_confirmation",
                ],
                "properties": {
                    "id": {"type": "integer"},
                    "action": {"type": "string", "enum": ["move", "skip", "delete"]},
                    "source_path": {"type": "string"},
                    "destination_path": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "needs_user_confirmation": {"type": "boolean"},
                },
            },
        },
    },
}

