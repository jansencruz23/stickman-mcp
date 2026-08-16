import anyio

from stickman_mcp import server

TOOLS = {
    "stickman_create_run": ["topic"],
    "stickman_save_script": ["run_id", "script"],
    "stickman_get_run": ["run_id"],
    "stickman_synthesize_narration": ["run_id"],
    "stickman_generate_images": ["run_id"],
    "stickman_job_status": ["run_id"],
    "stickman_regenerate_image": ["run_id", "scene_id"],
    "stickman_render_video": ["run_id"],
    "stickman_list_music": [],
    "stickman_save_metadata": ["run_id", "title", "description", "tags"],
}


def test_every_tool_is_registered_with_a_description_and_required_arguments():
    tools = {tool.name: tool for tool in anyio.run(server.server.list_tools)}

    assert set(tools) == set(TOOLS)
    for name, required in TOOLS.items():
        assert tools[name].description, f"{name} has no description"
        assert tools[name].input_schema.get("required", []) == required
