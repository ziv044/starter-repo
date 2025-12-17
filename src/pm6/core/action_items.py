"""Action Items System for Structured Agent Outputs.

Transforms raw agent responses into typed, actionable items:
- INFO: Display-only status updates
- METRIC_UPDATE: World state changes (auto-applied)
- APPROVAL: Authorization requests (approve/deny)
- DEMAND: Stakeholder demands (agree/disagree each)
- OPTION: Multiple choice selection (pick one)
- OPERATION: Time-bound operations (authorize → track)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal


class ActionItemType(str, Enum):
    """Types of action items extracted from agent responses."""

    INFO = "info"
    METRIC_UPDATE = "metric_update"
    APPROVAL = "approval"
    DEMAND = "demand"
    OPTION = "option"
    OPERATION = "operation"


class ActionItemStatus(str, Enum):
    """Status of an action item."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    AGREED = "agreed"
    DISAGREED = "disagreed"
    SELECTED = "selected"
    DEFERRED = "deferred"
    APPLIED = "applied"  # For metric updates
    ACKNOWLEDGED = "acknowledged"  # For info items
    CANCELLED = "cancelled"  # For cancelled operations
    RESOLVED = "resolved"  # Generic resolution
    IN_PROGRESS = "in_progress"  # For active operations


class OperationStatus(str, Enum):
    """Status of an active operation."""

    PROPOSED = "proposed"
    AUTHORIZED = "authorized"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationCategory(str, Enum):
    """Category of operation for visual badging."""

    CYBER = "cyber"
    KINETIC = "kinetic"
    HUMINT = "humint"
    SIGINT = "sigint"
    RECON = "recon"
    RESCUE = "rescue"
    DIPLOMATIC = "diplomatic"


class UrgencyLevel(str, Enum):
    """Urgency level for visual priority."""

    CRITICAL = "critical"  # Red
    HIGH = "high"  # Orange
    MEDIUM = "medium"  # Yellow
    LOW = "low"  # Blue
    ROUTINE = "routine"  # Gray


class ClassificationLevel(str, Enum):
    """Classification level for document styling."""

    TOP_SECRET = "top_secret"
    SECRET = "secret"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    UNCLASSIFIED = "unclassified"


@dataclass
class ImpactPreview:
    """Predicted impact on world state metrics."""

    metric: str
    change: int | float
    is_positive: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_positive = self.change >= 0

    def toDict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "change": self.change,
            "is_positive": self.is_positive,
        }


@dataclass
class DemandItem:
    """A single demand within a DEMAND action item."""

    id: str
    text: str
    agree_impacts: list[ImpactPreview] = field(default_factory=list)
    disagree_impacts: list[ImpactPreview] = field(default_factory=list)
    response: Literal["pending", "agreed", "disagreed"] = "pending"

    def toDict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "agree_impacts": [i.toDict() for i in self.agree_impacts],
            "disagree_impacts": [i.toDict() for i in self.disagree_impacts],
            "response": self.response,
        }


@dataclass
class OptionItem:
    """A single option within an OPTION action item."""

    id: str
    text: str
    impacts: list[ImpactPreview] = field(default_factory=list)
    description: str = ""
    risk_level: str = "medium"

    def toDict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "impacts": [i.toDict() for i in self.impacts],
            "description": self.description,
            "risk_level": self.risk_level,
        }


@dataclass
class ActionItem:
    """A structured action item extracted from agent response.

    This is the base class for all action items presented to the player.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ActionItemType = ActionItemType.INFO
    source_agent: str = ""
    source_role: str = ""
    title: str = ""
    content: str = ""
    status: ActionItemStatus = ActionItemStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: datetime | None = None

    # Visual styling
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    classification: ClassificationLevel = ClassificationLevel.CONFIDENTIAL

    # For APPROVAL type
    impacts: list[ImpactPreview] = field(default_factory=list)

    # For DEMAND type
    demands: list[DemandItem] = field(default_factory=list)
    warning_text: str = ""  # e.g., "Mass demonstration tomorrow"

    # For OPTION type
    options: list[OptionItem] = field(default_factory=list)
    option_group_id: str = ""  # Links options together

    # For METRIC_UPDATE type
    metric_key: str = ""
    metric_value: Any = None
    metric_old_value: Any = None

    # For OPERATION type (proposal stage)
    operation_codename: str = ""
    operation_category: OperationCategory | None = None
    operation_duration_hours: int = 0
    operation_description: str = ""
    operation_expected_outcome: str = ""

    # Reference to active operation (set when authorized)
    active_operation: ActiveOperation | None = None

    def resolve(self, status: ActionItemStatus) -> None:
        """Mark this item as resolved with given status."""
        self.status = status
        self.resolved_at = datetime.now()

    def is_pending(self) -> bool:
        """Check if this item still needs action."""
        return self.status == ActionItemStatus.PENDING

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "source_agent": self.source_agent,
            "source_role": self.source_role,
            "title": self.title,
            "content": self.content,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "urgency": self.urgency.value,
            "classification": self.classification.value,
            "impacts": [i.toDict() for i in self.impacts],
            "approval_impacts": {i.metric: i.change for i in self.impacts},  # Flat dict for UI
            "demands": [d.toDict() for d in self.demands],
            "demand_items": [d.toDict() for d in self.demands],  # Alias for UI
            "warning_text": self.warning_text,
            "deadline_warning": self.warning_text,  # Alias for UI
            "options": [o.toDict() for o in self.options],
            "option_group_id": self.option_group_id,
            "metric_key": self.metric_key,
            "metric_value": self.metric_value,
            "metric_old_value": self.metric_old_value,
            "operation_codename": self.operation_codename,
            "operation_name": self.title,  # Alias for UI
            "operation_category": self.operation_category.value if self.operation_category else None,
            "operation_duration": self.operation_duration_hours,  # Alias for UI
            "operation_duration_hours": self.operation_duration_hours,
            "operation_description": self.operation_description,
            "operation_expected_outcome": self.operation_expected_outcome,
            "active_operation": self.active_operation.toDict() if self.active_operation else None,
        }

    # Snake case alias for API consistency
    def to_dict(self) -> dict[str, Any]:
        """Snake case alias for toDict()."""
        return self.toDict()

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> ActionItem:
        """Create ActionItem from dictionary."""
        item = cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=ActionItemType(data.get("type", "info")),
            source_agent=data.get("source_agent", ""),
            source_role=data.get("source_role", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            status=ActionItemStatus(data.get("status", "pending")),
            urgency=UrgencyLevel(data.get("urgency", "medium")),
            classification=ClassificationLevel(data.get("classification", "confidential")),
            metric_key=data.get("metric_key", ""),
            metric_value=data.get("metric_value"),
            operation_codename=data.get("operation_codename", ""),
            operation_duration_hours=data.get("operation_duration_hours", 0),
            operation_description=data.get("operation_description", ""),
            operation_expected_outcome=data.get("operation_expected_outcome", ""),
            warning_text=data.get("warning_text", ""),
        )

        # Parse impacts
        for impact_data in data.get("impacts", []):
            item.impacts.append(ImpactPreview(
                metric=impact_data["metric"],
                change=impact_data["change"],
            ))

        # Parse demands
        for demand_data in data.get("demands", []):
            demand = DemandItem(
                id=demand_data["id"],
                text=demand_data["text"],
                response=demand_data.get("response", "pending"),
            )
            for ai in demand_data.get("agree_impacts", []):
                demand.agree_impacts.append(ImpactPreview(metric=ai["metric"], change=ai["change"]))
            for di in demand_data.get("disagree_impacts", []):
                demand.disagree_impacts.append(ImpactPreview(metric=di["metric"], change=di["change"]))
            item.demands.append(demand)

        # Parse options
        for option_data in data.get("options", []):
            option = OptionItem(
                id=option_data["id"],
                text=option_data["text"],
                description=option_data.get("description", ""),
                risk_level=option_data.get("risk_level", "medium"),
            )
            for impact in option_data.get("impacts", []):
                option.impacts.append(ImpactPreview(metric=impact["metric"], change=impact["change"]))
            item.options.append(option)

        # Parse operation category
        if data.get("operation_category"):
            item.operation_category = OperationCategory(data["operation_category"])

        return item


@dataclass
class ActiveOperation:
    """An authorized operation being tracked over game time.

    Created when player authorizes an OPERATION action item.
    Tracked by OperationsTracker until completion/failure/cancellation.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    codename: str = ""
    category: OperationCategory = OperationCategory.RECON
    owner_agent: str = ""
    owner_role: str = ""
    description: str = ""

    # Timeline
    duration_hours: int = 48
    started_at: datetime = field(default_factory=datetime.now)
    started_turn: int = 0
    estimated_completion: datetime | None = None

    # Progress
    hours_elapsed: int = 0
    progress_percent: float = 0.0
    status: OperationStatus = OperationStatus.IN_PROGRESS

    # Outcome
    completion_event: str | None = None  # Event to trigger on completion
    expected_outcome: str = ""
    actual_outcome: str = ""  # Filled on completion

    # Complications (optional feature)
    complication_chance: float = 0.1
    complication_event: str | None = None
    has_complication: bool = False

    # Milestones for progress updates
    milestones: list[dict[str, Any]] = field(default_factory=list)
    current_milestone: int = 0

    def update_progress(self, hours_passed: int) -> bool:
        """Update operation progress based on hours passed.

        Returns True if operation completed this update.
        """
        if self.status != OperationStatus.IN_PROGRESS:
            return False

        self.hours_elapsed += hours_passed
        self.progress_percent = min(100.0, (self.hours_elapsed / self.duration_hours) * 100)

        # Check milestones
        for i, milestone in enumerate(self.milestones):
            if i > self.current_milestone and self.progress_percent >= milestone.get("percent", 0):
                self.current_milestone = i

        # Check completion
        if self.hours_elapsed >= self.duration_hours:
            self.status = OperationStatus.COMPLETED
            self.progress_percent = 100.0
            return True

        return False

    def cancel(self, reason: str = "") -> None:
        """Cancel this operation."""
        self.status = OperationStatus.CANCELLED
        self.actual_outcome = f"Cancelled: {reason}" if reason else "Cancelled by player"

    def fail(self, reason: str = "") -> None:
        """Mark operation as failed."""
        self.status = OperationStatus.FAILED
        self.actual_outcome = f"Failed: {reason}" if reason else "Operation failed"

    def complete(self, outcome: str = "") -> None:
        """Mark operation as successfully completed."""
        self.status = OperationStatus.COMPLETED
        self.progress_percent = 100.0
        self.actual_outcome = outcome or self.expected_outcome

    def is_active(self) -> bool:
        """Check if operation is still running."""
        return self.status == OperationStatus.IN_PROGRESS

    def get_eta_hours(self) -> int:
        """Get estimated hours remaining."""
        return max(0, self.duration_hours - self.hours_elapsed)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "codename": self.codename,
            "category": self.category.value,
            "owner_agent": self.owner_agent,
            "owner_role": self.owner_role,
            "description": self.description,
            "duration_hours": self.duration_hours,
            "started_at": self.started_at.isoformat(),
            "started_turn": self.started_turn,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "hours_elapsed": self.hours_elapsed,
            "progress_percent": self.progress_percent,
            "status": self.status.value,
            "completion_event": self.completion_event,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "complication_chance": self.complication_chance,
            "has_complication": self.has_complication,
            "milestones": self.milestones,
            "current_milestone": self.current_milestone,
            "eta_hours": self.get_eta_hours(),
        }

    # Snake case alias for API consistency
    def to_dict(self) -> dict[str, Any]:
        """Snake case alias for toDict()."""
        return self.toDict()

    @classmethod
    def fromActionItem(cls, item: ActionItem, turn: int) -> ActiveOperation:
        """Create ActiveOperation from an authorized OPERATION action item."""
        from datetime import timedelta

        started = datetime.now()
        estimated = started + timedelta(hours=item.operation_duration_hours)

        return cls(
            id=f"op-{item.id}",
            name=item.title,
            codename=item.operation_codename,
            category=item.operation_category or OperationCategory.RECON,
            owner_agent=item.source_agent,
            owner_role=item.source_role,
            description=item.operation_description or item.content,
            duration_hours=item.operation_duration_hours,
            started_at=started,
            started_turn=turn,
            estimated_completion=estimated,
            expected_outcome=item.operation_expected_outcome,
        )

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> ActiveOperation:
        """Create ActiveOperation from dictionary."""
        op = cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            codename=data.get("codename", ""),
            category=OperationCategory(data.get("category", "recon")),
            owner_agent=data.get("owner_agent", ""),
            owner_role=data.get("owner_role", ""),
            description=data.get("description", ""),
            duration_hours=data.get("duration_hours", 48),
            started_turn=data.get("started_turn", 0),
            hours_elapsed=data.get("hours_elapsed", 0),
            progress_percent=data.get("progress_percent", 0.0),
            status=OperationStatus(data.get("status", "in_progress")),
            completion_event=data.get("completion_event"),
            expected_outcome=data.get("expected_outcome", ""),
            actual_outcome=data.get("actual_outcome", ""),
            complication_chance=data.get("complication_chance", 0.1),
            has_complication=data.get("has_complication", False),
            milestones=data.get("milestones", []),
            current_milestone=data.get("current_milestone", 0),
        )

        if data.get("started_at"):
            op.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("estimated_completion"):
            op.estimated_completion = datetime.fromisoformat(data["estimated_completion"])

        return op


# Factory functions for common action item types


def create_info_item(
    source_agent: str,
    source_role: str,
    content: str,
    title: str = "Intelligence Update",
) -> ActionItem:
    """Create an INFO action item (display only)."""
    return ActionItem(
        type=ActionItemType.INFO,
        source_agent=source_agent,
        source_role=source_role,
        title=title,
        content=content,
        classification=ClassificationLevel.CONFIDENTIAL,
    )


def create_metric_update(
    source_agent: str,
    source_role: str,
    metric_key: str,
    new_value: Any,
    old_value: Any = None,
    content: str = "",
) -> ActionItem:
    """Create a METRIC_UPDATE action item (auto-applied)."""
    return ActionItem(
        type=ActionItemType.METRIC_UPDATE,
        source_agent=source_agent,
        source_role=source_role,
        title=f"Update: {metric_key}",
        content=content or f"{metric_key} updated to {new_value}",
        metric_key=metric_key,
        metric_value=new_value,
        metric_old_value=old_value,
        status=ActionItemStatus.APPLIED,
    )


def create_approval_request(
    source_agent: str,
    source_role: str,
    title: str,
    content: str,
    impacts: dict[str, int | float],
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    classification: ClassificationLevel = ClassificationLevel.CONFIDENTIAL,
) -> ActionItem:
    """Create an APPROVAL action item."""
    item = ActionItem(
        type=ActionItemType.APPROVAL,
        source_agent=source_agent,
        source_role=source_role,
        title=title,
        content=content,
        urgency=urgency,
        classification=classification,
    )
    for metric, change in impacts.items():
        item.impacts.append(ImpactPreview(metric=metric, change=change))
    return item


def create_demand_item(
    source_agent: str,
    source_role: str,
    title: str,
    demands: list[dict[str, Any]],
    warning_text: str = "",
) -> ActionItem:
    """Create a DEMAND action item with multiple demands."""
    item = ActionItem(
        type=ActionItemType.DEMAND,
        source_agent=source_agent,
        source_role=source_role,
        title=title,
        content=f"{len(demands)} demands require response",
        urgency=UrgencyLevel.HIGH,
        warning_text=warning_text,
    )
    for i, d in enumerate(demands):
        demand = DemandItem(
            id=f"d{i+1}",
            text=d["text"],
        )
        for metric, change in d.get("agree_impacts", {}).items():
            demand.agree_impacts.append(ImpactPreview(metric=metric, change=change))
        for metric, change in d.get("disagree_impacts", {}).items():
            demand.disagree_impacts.append(ImpactPreview(metric=metric, change=change))
        item.demands.append(demand)
    return item


def create_option_item(
    source_agent: str,
    source_role: str,
    title: str,
    content: str,
    options: list[dict[str, Any]],
) -> ActionItem:
    """Create an OPTION action item (choose one)."""
    item = ActionItem(
        type=ActionItemType.OPTION,
        source_agent=source_agent,
        source_role=source_role,
        title=title,
        content=content,
        option_group_id=str(uuid.uuid4())[:8],
    )
    for i, o in enumerate(options):
        opt = OptionItem(
            id=f"opt{i+1}",
            text=o["text"],
            description=o.get("description", ""),
            risk_level=o.get("risk_level", "medium"),
        )
        for metric, change in o.get("impacts", {}).items():
            opt.impacts.append(ImpactPreview(metric=metric, change=change))
        item.options.append(opt)
    return item


def create_operation_proposal(
    source_agent: str,
    source_role: str,
    codename: str,
    category: OperationCategory,
    description: str,
    duration_hours: int,
    expected_outcome: str,
    classification: ClassificationLevel = ClassificationLevel.TOP_SECRET,
) -> ActionItem:
    """Create an OPERATION action item (proposal)."""
    return ActionItem(
        type=ActionItemType.OPERATION,
        source_agent=source_agent,
        source_role=source_role,
        title=f"Operation {codename}",
        content=description,
        classification=classification,
        operation_codename=codename,
        operation_category=category,
        operation_duration_hours=duration_hours,
        operation_description=description,
        operation_expected_outcome=expected_outcome,
    )
