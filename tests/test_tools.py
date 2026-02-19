"""Tests for tool implementations."""

import tempfile
from pathlib import Path

from agent_verify.tools import create_default_toolset
from agent_verify.tools.file_ops import FileEditTool, FileReadTool, FileWriteTool
from agent_verify.tools.bash import BashTool


def test_file_read_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool(tmpdir)
        read_tool = FileReadTool(tmpdir)

        result = write_tool.execute(path="test.txt", content="hello world")
        assert "Successfully" in result

        result = read_tool.execute(path="test.txt")
        assert result == "hello world"


def test_file_read_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        read_tool = FileReadTool(tmpdir)
        result = read_tool.execute(path="nonexistent.txt")
        assert "Error" in result


def test_file_edit():
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool(tmpdir)
        edit_tool = FileEditTool(tmpdir)
        read_tool = FileReadTool(tmpdir)

        write_tool.execute(path="test.py", content="def foo():\n    return 1\n")
        edit_tool.execute(path="test.py", old_string="return 1", new_string="return 42")
        result = read_tool.execute(path="test.py")
        assert "return 42" in result


def test_bash_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        bash = BashTool(tmpdir)
        result = bash.execute(command="echo hello")
        assert "hello" in result


def test_bash_tool_exit_code():
    with tempfile.TemporaryDirectory() as tmpdir:
        bash = BashTool(tmpdir)
        result = bash.execute(command="exit 1")
        assert "Exit code: 1" in result


def test_toolset():
    with tempfile.TemporaryDirectory() as tmpdir:
        toolset = create_default_toolset(tmpdir)
        assert "file_read" in toolset.tool_names
        assert "file_write" in toolset.tool_names
        assert "file_edit" in toolset.tool_names
        assert "bash" in toolset.tool_names
        schemas = toolset.to_api_schemas()
        assert len(schemas) == 4
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema
