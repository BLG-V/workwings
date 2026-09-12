from __future__ import annotations

from mawp.llm.anthropic_adapter import AnthropicAdapter


def test_to_anthropic_messages_batches_tool_results() -> None:
    messages = [
        {"role": "user", "content": "analyze repo"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_01", "name": "list_dir", "arguments": {"path": "."}},
                {"id": "call_02", "name": "read_file", "arguments": {"path": "a.py"}},
            ],
        },
        {"role": "tool", "tool_call_id": "call_01", "content": '{"success": true}'},
        {"role": "tool", "tool_call_id": "call_02", "content": '{"success": true}'},
    ]

    converted = AnthropicAdapter._to_anthropic_messages(messages)

    assert len(converted) == 3
    assert converted[0] == {"role": "user", "content": "analyze repo"}
    assert converted[1]["role"] == "assistant"
    assert len(converted[1]["content"]) == 2
    assert converted[2]["role"] == "user"
    assert len(converted[2]["content"]) == 2
    assert converted[2]["content"][0]["type"] == "tool_result"
    assert converted[2]["content"][0]["tool_use_id"] == "call_01"
    assert converted[2]["content"][1]["tool_use_id"] == "call_02"
