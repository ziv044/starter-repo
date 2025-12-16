"""Tool registry for Claude Skills integration.

Provides a framework for defining and executing tools that agents can use.
Supports FR9: Agents can access tools (database, files) via Claude Skills.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger("pm6.tools")


@dataclass
class Tool:
    """Definition of a tool that an agent can use.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description of what the tool does.
        inputSchema: JSON Schema defining the tool's input parameters.
        handler: Function that executes the tool.
        requiresConfirmation: Whether to ask for confirmation before executing.
    """

    name: str
    description: str
    inputSchema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    requiresConfirmation: bool = False

    def toDict(self) -> dict[str, Any]:
        """Convert to Anthropic API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.inputSchema,
        }

    def execute(self, inputs: dict[str, Any]) -> Any:
        """Execute the tool with given inputs.

        Args:
            inputs: Input parameters matching the tool's schema.

        Returns:
            Result of the tool execution.
        """
        logger.debug(f"Executing tool {self.name} with inputs: {inputs}")
        return self.handler(inputs)


@dataclass
class ToolCall:
    """A request from the model to use a tool.

    Attributes:
        id: Unique identifier for this tool use.
        name: Name of the tool to call.
        inputs: Input parameters for the tool.
    """

    id: str
    name: str
    inputs: dict[str, Any]

    @classmethod
    def fromContentBlock(cls, block: dict[str, Any]) -> "ToolCall":
        """Create from Anthropic API content block.

        Args:
            block: Content block with type="tool_use".

        Returns:
            ToolCall instance.
        """
        return cls(
            id=block["id"],
            name=block["name"],
            inputs=block.get("input", {}),
        )

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "inputs": self.inputs,
        }


@dataclass
class ToolResult:
    """Result of executing a tool.

    Attributes:
        toolUseId: ID of the tool call this is a result for.
        content: Result content (string or structured data).
        isError: Whether the tool execution failed.
        error: Error message if execution failed.
    """

    toolUseId: str
    content: Any
    isError: bool = False
    error: str = ""

    def toContentBlock(self) -> dict[str, Any]:
        """Convert to Anthropic API content block format."""
        if self.isError:
            return {
                "type": "tool_result",
                "tool_use_id": self.toolUseId,
                "content": self.error,
                "is_error": True,
            }
        else:
            contentStr = (
                self.content
                if isinstance(self.content, str)
                else json.dumps(self.content)
            )
            return {
                "type": "tool_result",
                "tool_use_id": self.toolUseId,
                "content": contentStr,
            }

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "toolUseId": self.toolUseId,
            "content": self.content,
            "isError": self.isError,
            "error": self.error,
        }


@dataclass
class ToolExecution:
    """Record of a tool execution.

    Attributes:
        toolCall: The tool call that was executed.
        result: The result of execution.
        durationMs: Execution time in milliseconds.
        timestamp: When the tool was executed.
    """

    toolCall: ToolCall
    result: ToolResult
    durationMs: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "toolCall": self.toolCall.toDict(),
            "result": self.result.toDict(),
            "durationMs": self.durationMs,
            "timestamp": self.timestamp.isoformat(),
        }


class ToolRegistry:
    """Registry of tools available to agents.

    Manages tool definitions and executes tool calls from the model.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(Tool(
        ...     name="get_weather",
        ...     description="Get current weather for a location",
        ...     inputSchema={
        ...         "type": "object",
        ...         "properties": {
        ...             "location": {"type": "string", "description": "City name"}
        ...         },
        ...         "required": ["location"]
        ...     },
        ...     handler=lambda inputs: {"temp": 72, "conditions": "sunny"}
        ... ))
        >>> tools = registry.getToolsForApi()
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._executions: list[ToolExecution] = []

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool to register.

        Raises:
            ValueError: If tool with same name already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> None:
        """Unregister a tool.

        Args:
            name: Name of tool to remove.
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")

    def get(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool if found, None otherwise.
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name.

        Returns:
            True if registered.
        """
        return name in self._tools

    def getToolsForApi(self) -> list[dict[str, Any]]:
        """Get tool definitions for Anthropic API.

        Returns:
            List of tool definitions in API format.
        """
        return [tool.toDict() for tool in self._tools.values()]

    def getToolNames(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    def execute(self, toolCall: ToolCall) -> ToolResult:
        """Execute a tool call.

        Args:
            toolCall: The tool call to execute.

        Returns:
            Result of the tool execution.
        """
        import time

        tool = self._tools.get(toolCall.name)

        if tool is None:
            result = ToolResult(
                toolUseId=toolCall.id,
                content="",
                isError=True,
                error=f"Tool '{toolCall.name}' not found",
            )
            logger.error(f"Tool not found: {toolCall.name}")
            return result

        startTime = time.perf_counter()

        try:
            output = tool.execute(toolCall.inputs)
            result = ToolResult(
                toolUseId=toolCall.id,
                content=output,
            )
            logger.debug(f"Tool {toolCall.name} executed successfully")

        except Exception as e:
            result = ToolResult(
                toolUseId=toolCall.id,
                content="",
                isError=True,
                error=str(e),
            )
            logger.error(f"Tool {toolCall.name} failed: {e}")

        durationMs = (time.perf_counter() - startTime) * 1000

        # Record execution
        execution = ToolExecution(
            toolCall=toolCall,
            result=result,
            durationMs=durationMs,
        )
        self._executions.append(execution)

        return result

    def executeMany(self, toolCalls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls.

        Args:
            toolCalls: List of tool calls to execute.

        Returns:
            List of results in same order.
        """
        return [self.execute(call) for call in toolCalls]

    def parseToolCalls(self, content: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse tool calls from response content.

        Args:
            content: List of content blocks from API response.

        Returns:
            List of tool calls found.
        """
        calls = []
        for block in content:
            if block.get("type") == "tool_use":
                calls.append(ToolCall.fromContentBlock(block))
        return calls

    def hasToolCalls(self, content: list[dict[str, Any]]) -> bool:
        """Check if response contains tool calls.

        Args:
            content: List of content blocks from API response.

        Returns:
            True if any tool_use blocks present.
        """
        return any(block.get("type") == "tool_use" for block in content)

    def formatResultsMessage(
        self, results: list[ToolResult]
    ) -> dict[str, Any]:
        """Format tool results as an assistant message.

        Args:
            results: List of tool results.

        Returns:
            Message dict with tool_result content blocks.
        """
        return {
            "role": "user",
            "content": [result.toContentBlock() for result in results],
        }

    def getExecutionHistory(self) -> list[ToolExecution]:
        """Get history of tool executions.

        Returns:
            List of execution records.
        """
        return list(self._executions)

    def getStats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with statistics.
        """
        if not self._executions:
            return {
                "totalExecutions": 0,
                "successCount": 0,
                "errorCount": 0,
                "avgDurationMs": 0.0,
            }

        successCount = sum(
            1 for e in self._executions if not e.result.isError
        )
        errorCount = len(self._executions) - successCount
        avgDuration = sum(e.durationMs for e in self._executions) / len(
            self._executions
        )

        return {
            "totalExecutions": len(self._executions),
            "successCount": successCount,
            "errorCount": errorCount,
            "avgDurationMs": avgDuration,
            "toolsRegistered": len(self._tools),
        }

    def clear(self) -> None:
        """Clear execution history."""
        self._executions.clear()

    def clearAll(self) -> None:
        """Clear both tools and execution history."""
        self._tools.clear()
        self._executions.clear()


def createTool(
    name: str,
    description: str,
    parameters: dict[str, dict[str, Any]],
    required: list[str] | None = None,
    handler: Callable[[dict[str, Any]], Any] | None = None,
) -> Tool:
    """Helper to create a tool with common patterns.

    Args:
        name: Tool name.
        description: Tool description.
        parameters: Dict mapping param names to their schemas.
        required: List of required parameter names.
        handler: Function to execute the tool.

    Returns:
        Configured Tool instance.

    Example:
        >>> tool = createTool(
        ...     name="lookup_user",
        ...     description="Look up a user by ID",
        ...     parameters={
        ...         "userId": {"type": "string", "description": "User ID"}
        ...     },
        ...     required=["userId"],
        ...     handler=lambda inputs: {"name": "John", "id": inputs["userId"]}
        ... )
    """
    inputSchema = {
        "type": "object",
        "properties": parameters,
    }
    if required:
        inputSchema["required"] = required

    return Tool(
        name=name,
        description=description,
        inputSchema=inputSchema,
        handler=handler or (lambda x: x),
    )
