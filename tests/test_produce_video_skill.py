"""The skill and README describe the tool surface; these keep the descriptions from going stale."""

import re
from pathlib import Path

import anyio

from stickman_mcp import server

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".claude" / "skills" / "produce-video" / "SKILL.md"
README = REPO / "README.md"

# The server's own name shares the prefix but is not a tool.
TOOL_MENTION = re.compile(r"stickman_(?!mcp\b)[a-z_]+")
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")


def registered_tools() -> set[str]:
    return {tool.name for tool in anyio.run(server.server.list_tools)}


def tools_named_in(document: Path) -> set[str]:
    return set(TOOL_MENTION.findall(document.read_text(encoding="utf-8")))


def test_the_skill_is_a_model_invocable_skill_named_for_the_command_the_creator_types():
    frontmatter = SKILL.read_text(encoding="utf-8").split("---")[1]

    assert re.search(r"^name: produce-video$", frontmatter, re.MULTILINE)
    assert re.search(r"^description: \S.*\S$", frontmatter, re.MULTILINE)
    assert "disable-model-invocation" not in frontmatter  # the creator triggers it by asking for a video


def test_the_skill_drives_tools_the_server_actually_registers():
    mentioned = tools_named_in(SKILL)

    assert mentioned, "the skill names no tools at all"
    unknown = mentioned - registered_tools()
    assert not unknown, f"the skill drives tools the server does not have: {sorted(unknown)}"


def test_the_readme_documents_every_tool_and_only_the_tools_that_exist():
    disagreement = tools_named_in(README) ^ registered_tools()

    assert not disagreement, f"README and tool surface disagree: {sorted(disagreement)}"


def test_every_document_the_skill_points_at_is_where_it_says_it_is():
    targets = MARKDOWN_LINK.findall(SKILL.read_text(encoding="utf-8"))
    relative = [target for target in targets if not target.startswith(("#", "http"))]

    assert relative, "the skill points at no documents"
    for target in relative:
        assert (SKILL.parent / target).exists(), f"{target} does not exist"


HEADING = re.compile(r"^#+ (.+)$", re.MULTILINE)
ANCHOR_LINK = re.compile(r"\]\((#[^)]+)\)")


def test_every_section_the_skill_points_at_within_itself_exists():
    """A renamed heading breaks a cross-reference silently, and the skill leans on them to stay short."""
    text = SKILL.read_text(encoding="utf-8")
    headings = {"#" + re.sub(r"[^a-z0-9 -]", "", name.lower()).replace(" ", "-") for name in HEADING.findall(text)}

    missing = sorted(set(ANCHOR_LINK.findall(text)) - headings)

    assert not missing, f"the skill points at sections it does not have: {missing}"
