"""Trimming unused projectors must not expose host files or tool arguments."""

import asyncio

from modict import MISSING, modict

from the_harness.plugins.client_remote.policy import RemoteProjection, wire_mapping


def test_wire_mapping_evaluates_computed_fields_and_omits_missing_values():
    class Payload(modict):
        @modict.computed
        def label(self):
            return "computed"

    assert wire_mapping(Payload(value=[MISSING, {"keep": 1, "missing": MISSING}])) == {
        "label": "computed", "value": [{"keep": 1}],
    }


def test_remote_history_withholds_local_media_and_projects_tool_feedback():
    items = [
        {"type": "message", "content": "Hello"},
        {"type": "image", "path": "/private/image.png"},
        {"type": "custom_file", "path": "/private/file.dat"},
        {"type": "function_call", "call_id": "tool", "name": "bash.command",
         "arguments": '{"user_feedback":" Reading files ","command":"private"}'},
    ]
    result = RemoteProjection().session_page("phone", {"before": "cursor", "turns": [{"id": "turn", "items": items}]})
    assert result["before"] == "cursor" and result["turns"][0]["id"] == "turn"
    assert result["turns"][0]["items"] == [items[0], {
        "kind": "tool_activity", "id": "tool-tool", "feedback": "Reading files", "status": "completed",
    }]


def test_remote_events_keep_envelopes_without_config_paths_or_tool_arguments():
    async def run():
        projection = RemoteProjection()
        def event(inner):
            return {"seq": 8, "v": 1, "payload": {"type": "command_event", "event": inner}}

        config = await projection.event("phone", event({"type": "agent.config.updated", "config": {"secret": "private"}}))
        assert config == {"seq": 8, "v": 1, "payload": {"type": "assistant_state", "assistant": {}}}
        image = await projection.event("phone", event({
            "type": "agent.response_item.added", "item": {"type": "image", "path": "/private/file", "description": "photo"},
        }))
        assert image["payload"]["event"]["item"] == {"type": "image", "description": "photo"}
        tool = await projection.event("phone", event({
            "type": "agent.tool_call.start", "user_feedback": "Reading", "tool_call": {
                "call_id": "tool", "name": "bash.command", "arguments": "private",
            },
        }))
        assert tool["payload"]["event"]["tool_call"] == {"call_id": "tool", "name": "bash.command"}
        assert tool["payload"]["event"]["user_feedback"] == "Reading"
        ordinary = event({"type": "agent.response_item.added", "item": {"type": "message", "content": "Hello"}})
        assert await projection.event("phone", ordinary) is ordinary

    asyncio.run(run())
