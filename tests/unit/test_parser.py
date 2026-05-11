"""Unit tests for Parser.

Covers: tool-call normal/error cases, text fence/XML blocks, mixed protocol,
empty command, 0/2+ actions.
"""

from __future__ import annotations

import pytest

from core.models import FormatError
from core.parser import parse_action


class TestToolCallMode:
    def test_single_bash_tool_call(self):
        msg = {
            "tool_calls": [
                {
                    "type": "bash",
                    "function": {"arguments": {"command": "echo hello"}},
                }
            ]
        }
        assert parse_action(msg, "tool-call") == "echo hello"

    def test_zero_tool_calls(self):
        msg = {"tool_calls": [], "content": "hello"}
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "tool-call")
        assert exc.value.error_type == "no_tool_call"

    def test_multiple_tool_calls(self):
        msg = {
            "tool_calls": [
                {"type": "bash", "function": {"arguments": {"command": "a"}}},
                {"type": "bash", "function": {"arguments": {"command": "b"}}},
            ]
        }
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "tool-call")
        assert exc.value.error_type == "multiple_tool_calls"

    def test_empty_command(self):
        msg = {
            "tool_calls": [
                {
                    "type": "bash",
                    "function": {"arguments": {"command": ""}},
                }
            ]
        }
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "tool-call")
        assert exc.value.error_type == "empty_command"

    def test_tool_call_and_text_conflict(self):
        msg = {
            "tool_calls": [
                {
                    "type": "bash",
                    "function": {"arguments": {"command": "echo hello"}},
                }
            ],
            "content": "```mswea_bash_command\necho hi\n```",
        }
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "tool-call")
        assert exc.value.error_type == "mixed_protocol"


class TestTextMode:
    def test_single_fence_block(self):
        msg = {"content": "```mswea_bash_command\necho hello\n```"}
        assert parse_action(msg, "text") == "echo hello"

    def test_single_xml_block(self):
        msg = {"content": "<mswea_bash_command>echo hello</mswea_bash_command>"}
        assert parse_action(msg, "text") == "echo hello"

    def test_fence_and_xml_conflict(self):
        msg = {
            "content": (
                "```mswea_bash_command\necho a\n```<mswea_bash_command>echo b</mswea_bash_command>"
            )
        }
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "text")
        assert exc.value.error_type == "mixed_protocol"

    def test_zero_blocks(self):
        msg = {"content": "just plain text"}
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "text")
        assert exc.value.error_type == "no_tool_call"

    def test_empty_fence_block(self):
        msg = {"content": "```mswea_bash_command\n\n```"}
        with pytest.raises(FormatError) as exc:
            parse_action(msg, "text")
        assert exc.value.error_type == "empty_command"
