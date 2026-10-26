"""youtube_kit 的开头评分、标题检查与钩子优先提示词。"""

import pytest

from app.services import llm, youtube_kit
from app.services.youtube_kit import hookscore, prompts


def test_formulas_load_from_packaged_json():
    formulas = hookscore.load_formulas()
    assert len(formulas) == 21
    assert all({"id", "name", "shape", "match"} <= set(f) for f in formulas)


def test_strong_hook_outscores_greeting():
    strong = youtube_kit.score_hook(
        "You are losing 40% of viewers in the first 8 seconds, and it is not your topic."
    )
    weak = youtube_kit.score_hook("Hey guys, welcome back to the channel, today we talk.")
    assert strong["verdict"] > weak["verdict"]
    assert weak["band"] == "WEAK"
    assert strong["formula"] == "The Statistic"


def test_score_reports_weakest_property_and_fix():
    result = youtube_kit.score_hook("Coffee.")
    assert result["weakest"] in result["properties"]
    assert result["fix"] == hookscore.FIX[result["weakest"]]
    assert result["properties"]["BREVITY"] < 100


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("", ""),
        (
            "Stop brewing coffee at boiling point. It burns the beans. Here is why.",
            "Stop brewing coffee at boiling point. It burns the beans.",
        ),
        (
            "Ninety percent of people brew coffee wrong, and you probably do too.\n\nMore.",
            "Ninety percent of people brew coffee wrong, and you probably do too.",
        ),
    ],
)
def test_extract_hook_takes_opening_until_hook_length(script, expected):
    assert youtube_kit.extract_hook(script) == expected


def test_non_latin_scripts_are_not_scored():
    assert youtube_kit.is_supported_text("Why your coffee tastes bitter")
    assert not youtube_kit.is_supported_text("为什么你的咖啡总是发苦")
    assert not youtube_kit.is_supported_text("123 !!!")


def test_title_lint_flags_duplicate_thumbnail_and_vague_words():
    result = youtube_kit.lint_title("The ultimate coffee guide", "COFFEE GUIDE")
    kinds = {kind for kind, _ in result["issues"]}
    assert {"duplicate", "vague", "no-number"} <= kinds


def test_title_lint_rewards_specific_short_title():
    good = youtube_kit.lint_title("I brewed coffee 30 ways in 7 days", "ONE WON")
    bad = youtube_kit.lint_title("THE ULTIMATE INSANE COFFEE GUIDE FOR EVERYONE")
    assert good["score"] > bad["score"]
    assert not good["issues"]


def test_hook_prompt_keeps_script_format_rules_and_drops_fabricating_formulas():
    prompt = youtube_kit.HOOK_FIRST_SCRIPT_SYSTEM_PROMPT
    assert len(prompt) <= llm.MAX_SCRIPT_SYSTEM_PROMPT_LENGTH
    assert "must not include any type of markdown" in prompt
    assert "respond in the same language as the video subject" in prompt
    assert "never invent a statistic" in prompt
    names = {f["id"]: f["name"] for f in hookscore.load_formulas()}
    for formula_id, name in names.items():
        listed = f"- {name}:" in prompt
        assert listed is (formula_id not in prompts.EXCLUDED_FORMULAS)


def test_hook_prompt_is_sent_as_custom_system_prompt():
    final = llm.build_script_prompt(
        video_subject="coffee",
        paragraph_number=2,
        custom_system_prompt=youtube_kit.HOOK_FIRST_SCRIPT_SYSTEM_PROMPT,
    )
    assert final.startswith("# Role: Video Script Generator (Hook First)")
    assert "- video subject: coffee" in final
