"""Tests for tool use support."""

import pytest

from pm6.tools import Tool, ToolCall, ToolRegistry, ToolResult
from pm6.tools.toolRegistry import ToolExecution, createTool


class TestTool:
    """Tests for Tool class."""

    def test_create_tool(self):
        """Test creating a basic tool."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
            },
            handler=lambda x: f"Got: {x['message']}",
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert not tool.requiresConfirmation

    def test_tool_to_dict(self):
        """Test converting tool to API format."""
        tool = Tool(
            name="get_data",
            description="Get some data",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"}
                },
                "required": ["id"],
            },
            handler=lambda x: {"data": "value"},
        )

        d = tool.toDict()

        assert d["name"] == "get_data"
        assert d["description"] == "Get some data"
        assert d["input_schema"]["type"] == "object"
        assert "id" in d["input_schema"]["properties"]

    def test_tool_execute(self):
        """Test executing a tool."""
        tool = Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
            },
            handler=lambda x: x["a"] + x["b"],
        )

        result = tool.execute({"a": 5, "b": 3})

        assert result == 8

    def test_tool_requires_confirmation(self):
        """Test tool with confirmation requirement."""
        tool = Tool(
            name="delete_file",
            description="Delete a file",
            inputSchema={"type": "object", "properties": {}},
            handler=lambda x: "deleted",
            requiresConfirmation=True,
        )

        assert tool.requiresConfirmation


class TestToolCall:
    """Tests for ToolCall class."""

    def test_create_tool_call(self):
        """Test creating a tool call."""
        call = ToolCall(
            id="call_123",
            name="get_weather",
            inputs={"location": "New York"},
        )

        assert call.id == "call_123"
        assert call.name == "get_weather"
        assert call.inputs["location"] == "New York"

    def test_from_content_block(self):
        """Test creating from API content block."""
        block = {
            "type": "tool_use",
            "id": "toolu_abc",
            "name": "search",
            "input": {"query": "test"},
        }

        call = ToolCall.fromContentBlock(block)

        assert call.id == "toolu_abc"
        assert call.name == "search"
        assert call.inputs["query"] == "test"

    def test_to_dict(self):
        """Test serialization to dict."""
        call = ToolCall(
            id="call_1",
            name="lookup",
            inputs={"key": "value"},
        )

        d = call.toDict()

        assert d["id"] == "call_1"
        assert d["name"] == "lookup"
        assert d["inputs"]["key"] == "value"


class TestToolResult:
    """Tests for ToolResult class."""

    def test_successful_result(self):
        """Test successful tool result."""
        result = ToolResult(
            toolUseId="call_1",
            content={"status": "ok"},
        )

        assert not result.isError
        assert result.content["status"] == "ok"

    def test_error_result(self):
        """Test error tool result."""
        result = ToolResult(
            toolUseId="call_1",
            content="",
            isError=True,
            error="Something went wrong",
        )

        assert result.isError
        assert result.error == "Something went wrong"

    def test_to_content_block_success(self):
        """Test converting success result to API format."""
        result = ToolResult(
            toolUseId="call_1",
            content={"data": 42},
        )

        block = result.toContentBlock()

        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "call_1"
        assert "42" in block["content"]
        assert "is_error" not in block

    def test_to_content_block_error(self):
        """Test converting error result to API format."""
        result = ToolResult(
            toolUseId="call_1",
            content="",
            isError=True,
            error="Not found",
        )

        block = result.toContentBlock()

        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "call_1"
        assert block["content"] == "Not found"
        assert block["is_error"] is True

    def test_string_content(self):
        """Test result with string content."""
        result = ToolResult(
            toolUseId="call_1",
            content="Plain text result",
        )

        block = result.toContentBlock()

        assert block["content"] == "Plain text result"


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = Tool(
            name="test",
            description="Test tool",
            inputSchema={"type": "object"},
            handler=lambda x: x,
        )

        registry.register(tool)

        assert registry.has("test")
        assert registry.get("test") == tool

    def test_register_duplicate_raises(self):
        """Test registering duplicate tool raises error."""
        registry = ToolRegistry()
        tool = Tool(
            name="test",
            description="Test",
            inputSchema={},
            handler=lambda x: x,
        )

        registry.register(tool)

        with pytest.raises(ValueError):
            registry.register(tool)

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()
        tool = Tool(
            name="test",
            description="Test",
            inputSchema={},
            handler=lambda x: x,
        )

        registry.register(tool)
        registry.unregister("test")

        assert not registry.has("test")

    def test_get_tools_for_api(self):
        """Test getting tools in API format."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="tool1",
            description="First tool",
            inputSchema={"type": "object"},
            handler=lambda x: x,
        ))
        registry.register(Tool(
            name="tool2",
            description="Second tool",
            inputSchema={"type": "object"},
            handler=lambda x: x,
        ))

        tools = registry.getToolsForApi()

        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"tool1", "tool2"}

    def test_get_tool_names(self):
        """Test getting tool names."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="alpha",
            description="Alpha",
            inputSchema={},
            handler=lambda x: x,
        ))
        registry.register(Tool(
            name="beta",
            description="Beta",
            inputSchema={},
            handler=lambda x: x,
        ))

        names = registry.getToolNames()

        assert "alpha" in names
        assert "beta" in names

    def test_execute_tool(self):
        """Test executing a tool through registry."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="multiply",
            description="Multiply two numbers",
            inputSchema={},
            handler=lambda x: x["a"] * x["b"],
        ))

        call = ToolCall(id="call_1", name="multiply", inputs={"a": 4, "b": 5})
        result = registry.execute(call)

        assert not result.isError
        assert result.content == 20

    def test_execute_unknown_tool(self):
        """Test executing unknown tool returns error."""
        registry = ToolRegistry()

        call = ToolCall(id="call_1", name="unknown", inputs={})
        result = registry.execute(call)

        assert result.isError
        assert "not found" in result.error

    def test_execute_tool_error(self):
        """Test handling tool execution error."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="failing",
            description="Always fails",
            inputSchema={},
            handler=lambda x: 1 / 0,
        ))

        call = ToolCall(id="call_1", name="failing", inputs={})
        result = registry.execute(call)

        assert result.isError
        assert "division" in result.error.lower()

    def test_execute_many(self):
        """Test executing multiple tool calls."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="double",
            description="Double a number",
            inputSchema={},
            handler=lambda x: x["n"] * 2,
        ))

        calls = [
            ToolCall(id="c1", name="double", inputs={"n": 5}),
            ToolCall(id="c2", name="double", inputs={"n": 10}),
        ]
        results = registry.executeMany(calls)

        assert len(results) == 2
        assert results[0].content == 10
        assert results[1].content == 20

    def test_parse_tool_calls(self):
        """Test parsing tool calls from response content."""
        registry = ToolRegistry()

        content = [
            {"type": "text", "text": "Let me help with that."},
            {"type": "tool_use", "id": "t1", "name": "search", "input": {"q": "test"}},
            {"type": "tool_use", "id": "t2", "name": "lookup", "input": {"id": "123"}},
        ]

        calls = registry.parseToolCalls(content)

        assert len(calls) == 2
        assert calls[0].name == "search"
        assert calls[1].name == "lookup"

    def test_has_tool_calls(self):
        """Test checking for tool calls in response."""
        registry = ToolRegistry()

        withTools = [
            {"type": "text", "text": "Here"},
            {"type": "tool_use", "id": "t1", "name": "test", "input": {}},
        ]
        withoutTools = [
            {"type": "text", "text": "Just text"},
        ]

        assert registry.hasToolCalls(withTools)
        assert not registry.hasToolCalls(withoutTools)

    def test_format_results_message(self):
        """Test formatting results as message."""
        registry = ToolRegistry()

        results = [
            ToolResult(toolUseId="t1", content="Result 1"),
            ToolResult(toolUseId="t2", content="Result 2"),
        ]

        message = registry.formatResultsMessage(results)

        assert message["role"] == "user"
        assert len(message["content"]) == 2
        assert message["content"][0]["type"] == "tool_result"

    def test_execution_history(self):
        """Test execution history tracking."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="echo",
            description="Echo input",
            inputSchema={},
            handler=lambda x: x,
        ))

        call = ToolCall(id="c1", name="echo", inputs={"msg": "hello"})
        registry.execute(call)

        history = registry.getExecutionHistory()

        assert len(history) == 1
        assert history[0].toolCall.name == "echo"
        assert history[0].durationMs > 0

    def test_get_stats(self):
        """Test getting execution statistics."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="ok",
            description="OK",
            inputSchema={},
            handler=lambda x: "ok",
        ))
        registry.register(Tool(
            name="fail",
            description="Fail",
            inputSchema={},
            handler=lambda x: 1 / 0,
        ))

        registry.execute(ToolCall(id="c1", name="ok", inputs={}))
        registry.execute(ToolCall(id="c2", name="ok", inputs={}))
        registry.execute(ToolCall(id="c3", name="fail", inputs={}))

        stats = registry.getStats()

        assert stats["totalExecutions"] == 3
        assert stats["successCount"] == 2
        assert stats["errorCount"] == 1
        assert stats["toolsRegistered"] == 2

    def test_get_stats_empty(self):
        """Test stats with no executions."""
        registry = ToolRegistry()

        stats = registry.getStats()

        assert stats["totalExecutions"] == 0
        assert stats["avgDurationMs"] == 0.0

    def test_clear(self):
        """Test clearing execution history."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="test",
            description="Test",
            inputSchema={},
            handler=lambda x: x,
        ))
        registry.execute(ToolCall(id="c1", name="test", inputs={}))

        registry.clear()

        assert len(registry.getExecutionHistory()) == 0
        assert registry.has("test")  # Tools still registered

    def test_clear_all(self):
        """Test clearing everything."""
        registry = ToolRegistry()
        registry.register(Tool(
            name="test",
            description="Test",
            inputSchema={},
            handler=lambda x: x,
        ))
        registry.execute(ToolCall(id="c1", name="test", inputs={}))

        registry.clearAll()

        assert len(registry.getExecutionHistory()) == 0
        assert not registry.has("test")


class TestCreateTool:
    """Tests for createTool helper function."""

    def test_create_basic_tool(self):
        """Test creating a basic tool."""
        tool = createTool(
            name="greet",
            description="Greet a user",
            parameters={
                "name": {"type": "string", "description": "Name to greet"}
            },
            handler=lambda x: f"Hello, {x['name']}!",
        )

        assert tool.name == "greet"
        assert tool.inputSchema["type"] == "object"
        assert "name" in tool.inputSchema["properties"]

    def test_create_tool_with_required(self):
        """Test creating tool with required parameters."""
        tool = createTool(
            name="lookup",
            description="Lookup by ID",
            parameters={
                "id": {"type": "string"},
                "optional": {"type": "string"},
            },
            required=["id"],
        )

        assert tool.inputSchema["required"] == ["id"]

    def test_create_tool_no_handler(self):
        """Test creating tool without handler returns identity."""
        tool = createTool(
            name="passthrough",
            description="Pass through inputs",
            parameters={},
        )

        result = tool.execute({"key": "value"})
        assert result == {"key": "value"}


class TestToolExecution:
    """Tests for ToolExecution class."""

    def test_execution_to_dict(self):
        """Test serializing execution to dict."""
        call = ToolCall(id="c1", name="test", inputs={"a": 1})
        result = ToolResult(toolUseId="c1", content="done")
        execution = ToolExecution(
            toolCall=call,
            result=result,
            durationMs=15.5,
        )

        d = execution.toDict()

        assert d["toolCall"]["name"] == "test"
        assert d["result"]["content"] == "done"
        assert d["durationMs"] == 15.5
        assert "timestamp" in d


class TestSimulationToolIntegration:
    """Tests for tool integration with Simulation."""

    def test_simulation_has_tool_registry(self, tmp_path):
        """Test simulation has tool registry."""
        from pm6 import Simulation

        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        assert sim.toolRegistry is not None

    def test_register_tool_via_simulation(self, tmp_path):
        """Test registering tools via simulation."""
        from pm6 import Simulation, Tool

        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        tool = Tool(
            name="greet",
            description="Greet someone",
            inputSchema={"type": "object"},
            handler=lambda x: f"Hello, {x.get('name', 'World')}!",
        )
        sim.registerTool(tool)

        assert sim.hasTool("greet")
        assert "greet" in sim.getRegisteredTools()

    def test_register_tool_from_function(self, tmp_path):
        """Test registering tool from function."""
        from pm6 import Simulation

        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        sim.registerToolFromFunction(
            name="add",
            description="Add two numbers",
            handler=lambda x: x["a"] + x["b"],
            parameters={
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            required=["a", "b"],
        )

        assert sim.hasTool("add")

    def test_execute_tool_via_simulation(self, tmp_path):
        """Test executing tool via simulation."""
        from pm6 import Simulation

        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        sim.registerToolFromFunction(
            name="multiply",
            description="Multiply two numbers",
            handler=lambda x: x["a"] * x["b"],
            parameters={"a": {"type": "number"}, "b": {"type": "number"}},
        )

        result = sim.executeTool("multiply", {"a": 6, "b": 7})

        assert not result.isError
        assert result.content == 42

    def test_unregister_tool(self, tmp_path):
        """Test unregistering tool."""
        from pm6 import Simulation, Tool

        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        sim.registerTool(Tool(
            name="temp",
            description="Temporary",
            inputSchema={},
            handler=lambda x: x,
        ))
        assert sim.hasTool("temp")

        sim.unregisterTool("temp")
        assert not sim.hasTool("temp")

    def test_get_tool_stats(self, tmp_path):
        """Test getting tool stats."""
        from pm6 import Simulation

        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        sim.registerToolFromFunction(
            name="echo",
            description="Echo input",
            handler=lambda x: x,
            parameters={},
        )
        sim.executeTool("echo", {"msg": "test"})

        stats = sim.getToolStats()

        assert stats["totalExecutions"] == 1
        assert stats["successCount"] == 1
