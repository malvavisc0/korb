"""Skill definitions shipped with the korb package."""

from importlib.resources import files

SKILL_MAP: dict[str, str] = {
    "analysis": "SKILL_TEAM_ANALYSIS.md",
    "prediction": "SKILL_LEAGUE_TOP_N_ANALYSIS.md",
}


def get_skill_text(name: str) -> str:
    """Return the markdown text of a named skill.

    Args:
        name: Skill key from SKILL_MAP (e.g. "analysis", "prediction").

    Returns:
        The full markdown content of the skill file.

    Raises:
        ValueError: If *name* is not in SKILL_MAP.
    """
    if name not in SKILL_MAP:
        raise ValueError(
            f"unknown skill: {name!r}. Choose from: {', '.join(SKILL_MAP)}"
        )
    filename = SKILL_MAP[name]
    return files(__package__).joinpath(filename).read_text(encoding="utf-8")
