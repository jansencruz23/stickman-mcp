import anyio

from stickman_mcp import server

LIFECYCLE_TOOLS = {
    "stickman_create_run": ["topic"],
    "stickman_save_script": ["run_id", "script"],
    "stickman_get_run": ["run_id"],
}


def test_lifecycle_tools_are_registered_with_descriptions_and_required_arguments():
    tools = {tool.name: tool for tool in anyio.run(server.server.list_tools)}

    assert set(tools) == set(LIFECYCLE_TOOLS)
    for name, required in LIFECYCLE_TOOLS.items():
        assert tools[name].description, f"{name} has no description"
        assert tools[name].input_schema["required"] == required
