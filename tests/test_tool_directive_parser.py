"""
Tests for the TOOL: directive parser in wow_tools.

Covers the echo-robust behavior needed for thinking-mode models: the parser
must select the LAST valid ``TOOL: {...}`` directive (ignoring an example
directive echoed inside a model's reasoning) and must extract balanced JSON
braces so nested objects and braces inside string values do not truncate the
capture. ``strip_tool_directive`` must remove every such directive span.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.integrations.wow_tools import (  # noqa: E402
    parse_tool_directive,
    strip_tool_directive,
)


def test_single_clean_directive():
    text = 'hello\n</think>\n\nTOOL: {"name":"crypto","args":{"symbol":"BTC"}}'
    assert parse_tool_directive(text) == ("crypto", {"symbol": "BTC"})


def test_echoed_example_then_real_directive():
    # Thinking-mode models echo the system-prompt example, then emit the real
    # directive last. The last valid one must win.
    text = (
        'End with: TOOL: {"name":"web_search","args":{"query":"..."}}\n'
        '</think>\n\nTOOL: {"name":"crypto","args":{"symbol":"BTC"}}'
    )
    assert parse_tool_directive(text) == ("crypto", {"symbol": "BTC"})


def test_nested_braces_in_args():
    text = 'TOOL: {"name":"calc","args":{"expression":"{a}+{b}"}}'
    assert parse_tool_directive(text) == ("calc", {"expression": "{a}+{b}"})


def test_braces_inside_string_value():
    text = 'TOOL: {"name":"web_search","args":{"query":"a } b { c"}}'
    assert parse_tool_directive(text) == ("web_search", {"query": "a } b { c"})


def test_fenced_tool_block():
    text = '```tool\n{"name":"time_now","args":{}}\n```'
    assert parse_tool_directive(text) == ("time_now", {})


def test_no_directive_returns_none():
    assert parse_tool_directive("just some prose, no tool here") is None


def test_tool_and_arguments_aliases():
    text = 'TOOL: {"tool":"wikipedia","arguments":{"query":"x"}}'
    assert parse_tool_directive(text) == ("wikipedia", {"query": "x"})


def test_strip_removes_directive_keeps_prose():
    text = 'Here you go.\n\nTOOL: {"name":"crypto","args":{"symbol":"BTC"}}'
    assert strip_tool_directive(text) == "Here you go."


def test_strip_removes_all_directive_spans():
    text = (
        'Note TOOL: {"name":"x","args":{}} then\n'
        'TOOL: {"name":"crypto","args":{"symbol":"BTC"}}'
    )
    assert strip_tool_directive(text) == "Note  then"
