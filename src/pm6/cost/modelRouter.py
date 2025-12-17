"""Model routing for cost optimization.

Routes tasks to appropriate models based on complexity:
- Haiku for routine tasks (summarization, compaction)
- Sonnet for agent responses (quality critical)
- Opus for complex reasoning (when needed)
"""

import logging
from enum import Enum

logger = logging.getLogger("pm6.cost")


class TaskType(str, Enum):
    """Types of tasks for model routing.

    Attributes:
        COMPACTION: Context compaction/summarization.
        SUMMARIZATION: History summarization.
        AGENT_RESPONSE: Main agent response generation.
        COMPLEX_REASONING: Complex analysis requiring highest capability.
    """

    COMPACTION = "compaction"
    SUMMARIZATION = "summarization"
    AGENT_RESPONSE = "agent_response"
    COMPLEX_REASONING = "complex_reasoning"


# Default model assignments
DEFAULT_MODEL_ROUTING = {
    TaskType.COMPACTION: "claude-haiku-3-20240307",
    TaskType.SUMMARIZATION: "claude-haiku-3-20240307",
    TaskType.AGENT_RESPONSE: "claude-sonnet-4-20250514",
    TaskType.COMPLEX_REASONING: "claude-sonnet-4-20250514",  # Can be upgraded to Opus
}


class ModelRouter:
    """Routes tasks to appropriate models.

    Args:
        routing: Custom task type to model mapping.
        defaultModel: Fallback model for unknown tasks.
    """

    def __init__(
        self,
        routing: dict[TaskType, str] | None = None,
        defaultModel: str = "claude-sonnet-4-20250514",
    ):
        self._routing = routing or DEFAULT_MODEL_ROUTING.copy()
        self._defaultModel = defaultModel

    def getModel(self, taskType: TaskType) -> str:
        """Get the model for a task type.

        Args:
            taskType: The type of task.

        Returns:
            Model identifier string.
        """
        model = self._routing.get(taskType, self._defaultModel)
        logger.debug(f"Routing {taskType.value} to {model}")
        return model

    def setModel(self, taskType: TaskType, model: str) -> None:
        """Set the model for a task type.

        Args:
            taskType: The type of task.
            model: Model identifier to use.
        """
        self._routing[taskType] = model
        logger.info(f"Updated routing: {taskType.value} -> {model}")

    def getRouting(self) -> dict[str, str]:
        """Get the current routing configuration.

        Returns:
            Dictionary of task type to model.
        """
        return {k.value: v for k, v in self._routing.items()}

    def isHaikuTask(self, taskType: TaskType) -> bool:
        """Check if a task routes to Haiku (cheap model).

        Args:
            taskType: The type of task.

        Returns:
            True if task uses Haiku.
        """
        model = self.getModel(taskType)
        return "haiku" in model.lower()

    def isSonnetTask(self, taskType: TaskType) -> bool:
        """Check if a task routes to Sonnet.

        Args:
            taskType: The type of task.

        Returns:
            True if task uses Sonnet.
        """
        model = self.getModel(taskType)
        return "sonnet" in model.lower()

    def isOpusTask(self, taskType: TaskType) -> bool:
        """Check if a task routes to Opus (expensive model).

        Args:
            taskType: The type of task.

        Returns:
            True if task uses Opus.
        """
        model = self.getModel(taskType)
        return "opus" in model.lower()
