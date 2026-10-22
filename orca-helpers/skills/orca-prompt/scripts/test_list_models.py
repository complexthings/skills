#!/usr/bin/env python3
"""Self-check for list_models.py. Run: python3 test_list_models.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from list_models import PRIORITY_PATH, RECOMMENDED_PATH, list_models, load_priority, slot_ranking

COLUMNS = """provider        model                       context  max-out  thinking  images
anthropic       claude-haiku-5-5            200K     64K      yes       yes
anthropic       claude-haiku-5-5-20261001   200K     64K      yes       yes
anthropic       claude-opus-5-5             1M       128K     yes       yes
github-copilot  claude-sonnet-5-5           1M       128K     yes       yes
"""

SLUGS = """opencode/claude-opus-5-5
opencode/claude-sonnet-5-5
google/gemini-3.8-flash
"""

PRIORITY = {
    "harnessOrder": ["claude"],
    "modelOrder": {
        "anthropic": {
            "orchestrationWorker": [
                {"model": "claude-opus-5-5", "effort": "medium"},
            ],
            "subagent": [
                {"model": "claude-opus-5-5", "effort": "low"},
                {"model": "claude-opus-5-5", "effort": "medium"},
                {"model": "claude-sonnet-5-5", "effort": "low"},
            ]
        }
    },
}

TABBED = """Fetching available models...
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)
gemini-3.8-flash-low\tGemini 3.8 Flash (Low)
claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)
"""

CONFIG_HELP = """  `logLevel`: log level for CLI; defaults to "default".

  `model`: AI model to use for Copilot CLI; can be changed with /model command or --model flag option.
    - "claude-sonnet-5.5"
    - "gpt-6-luna"
    - "kimi-k3"

  `contextTier`: context window tier for tiered-pricing models (e.g., "default" or "long_context").
    - Can also be set with --context flag (overrides persisted setting)
"""

COPILOT_PRIORITY = {
    "modelOrder": {
        "github-copilot": {
            "subagent": [
                {"model": "kimi-k3", "effort": "max"},
                {"model": "claude-haiku-4-5", "effort": None},
            ],
            "subagentSimple": [{"model": "claude-haiku-4.5", "effort": None}],
        }
    },
}


def test_columns_group_by_provider_and_drop_dated_aliases():
    providers = list_models("pi", COLUMNS)["providers"]
    assert sorted(providers) == ["anthropic", "github-copilot"]
    assert [e["model"] for e in providers["anthropic"]] == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert providers["anthropic"][0]["efforts"] == []


def test_slugs_split_provider_from_model():
    providers = list_models("opencode", SLUGS)["providers"]
    assert sorted(providers) == ["google", "opencode"]
    assert [e["model"] for e in providers["opencode"]] == ["claude-opus-5-5", "claude-sonnet-5-5"]


def test_agy_collapses_effort_suffixes_onto_one_entry():
    providers = list_models("agy", TABBED)["providers"]
    assert [e["model"] for e in providers["gemini"]] == ["gemini-3.8-flash"]
    assert providers["gemini"][0]["efforts"] == ["low", "medium", "high"]
    # A model with no effort suffix keeps its id and reports no efforts.
    assert providers["claude"] == [{"model": "claude-sonnet-4-6", "efforts": []}]


def test_copilot_reads_the_model_setting_choices():
    providers = list_models("copilot", CONFIG_HELP, "subagent", COPILOT_PRIORITY)["providers"]
    # Only the `model` block's bullets, not the `contextTier` one below it.
    assert [e["model"] for e in providers["github-copilot"]] == ["kimi-k3", "claude-sonnet-5.5", "gpt-6-luna"]
    assert providers["github-copilot"][0]["suggestedEffort"] == "max"


def test_copilot_falls_back_to_the_priority_file():
    providers = list_models("copilot", "error: not signed in\n", "subagent", COPILOT_PRIORITY)["providers"]
    # Each model once, even when the file spells it two ways across slots.
    assert [e["model"] for e in providers["github-copilot"]] == ["kimi-k3", "claude-haiku-4-5"]


def test_slot_ranks_known_models_first_and_keeps_unknown_ones():
    columns = COLUMNS + "anthropic       claude-sonnet-5-5           1M       128K     yes       yes\n"
    providers = list_models("pi", columns, "subagent", PRIORITY)["providers"]
    # Ranked models in file order; claude-haiku-5-5 is unranked, so it sorts last
    # rather than vanishing from the options.
    assert [e["model"] for e in providers["anthropic"]] == [
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    ]
    # The first entry for a model is the recommendation, even when the file
    # lists that model again at another effort.
    assert providers["anthropic"][0]["suggestedEffort"] == "low"
    assert "suggestedEffort" not in providers["anthropic"][2]
    # A provider the file says nothing about is left alphabetical, not emptied.
    assert [e["model"] for e in providers["github-copilot"]] == ["claude-sonnet-5-5"]


def test_main_orchestrator_reads_the_orchestration_worker_ranking():
    # No Priority File ranks the Main Orchestrator separately, so the slot
    # borrows `orchestrationWorker`'s order and suggested effort.
    providers = list_models("pi", COLUMNS, "mainOrchestrator", PRIORITY)["providers"]
    assert [e["model"] for e in providers["anthropic"]] == ["claude-opus-5-5", "claude-haiku-5-5"]
    assert providers["anthropic"][0]["suggestedEffort"] == "medium"


def test_ranking_matches_across_id_spellings():
    # Pi spells the same model `claude-sonnet-5-5` here and `claude-sonnet-5.5`
    # elsewhere; both must hit the same priority entry.
    columns = COLUMNS.replace("claude-opus-5-5", "claude-opus-5.5")
    providers = list_models("pi", columns, "subagent", PRIORITY)["providers"]
    assert providers["anthropic"][0] == {"model": "claude-opus-5.5", "efforts": [], "suggestedEffort": "low"}


def test_provider_aliases_reach_the_priority_file_keys():
    # opencode reports `google`, pi `openai`; the file ranks them as `gemini`, `openai-codex`.
    priority = {"modelOrder": {"gemini": {"subagent": [{"model": "m", "effort": "low"}]},
                               "openai-codex": {"subagent": [{"model": "g", "effort": "high"}]}}}
    assert slot_ranking(priority, "google", "subagent") == {"m": (0, "low")}
    assert slot_ranking(priority, "openai", "subagent") == {"g": (0, "high")}


def test_no_slot_leaves_the_report_alphabetical():
    providers = list_models("pi", COLUMNS, priority=PRIORITY)["providers"]
    assert [e["model"] for e in providers["anthropic"]] == ["claude-haiku-5-5", "claude-opus-5-5"]


def test_shipped_priority_file_covers_every_slot():
    # Both Priority Files ship and either can be the one Round 3 chooses.
    for path in (PRIORITY_PATH, RECOMMENDED_PATH):
        priority = load_priority(path)
        assert priority["harnessOrder"] == [
            "claude",
            "pi",
            "opencode",
            "copilot",
            "codex",
            "agy",
        ], path
        for provider, slots in priority["modelOrder"].items():
            for slot in ("orchestrationWorker", "subagent", "subagentSimple"):
                assert slots[slot], "%s in %s is missing %s" % (provider, path, slot)


def test_unknown_slot_is_an_error():
    try:
        list_models("pi", COLUMNS, "orchestrator", PRIORITY)
    except ValueError:
        return
    raise AssertionError("expected ValueError for an unknown Model Slot")


def test_unparseable_output_is_an_error():
    for bad in ("", "Fetching available models...\n"):
        try:
            list_models("pi", bad)
        except ValueError:
            continue
        raise AssertionError("expected ValueError for %r" % bad)


if __name__ == "__main__":
    test_columns_group_by_provider_and_drop_dated_aliases()
    test_slugs_split_provider_from_model()
    test_agy_collapses_effort_suffixes_onto_one_entry()
    test_copilot_reads_the_model_setting_choices()
    test_copilot_falls_back_to_the_priority_file()
    test_slot_ranks_known_models_first_and_keeps_unknown_ones()
    test_ranking_matches_across_id_spellings()
    test_main_orchestrator_reads_the_orchestration_worker_ranking()
    test_provider_aliases_reach_the_priority_file_keys()
    test_no_slot_leaves_the_report_alphabetical()
    test_shipped_priority_file_covers_every_slot()
    test_unknown_slot_is_an_error()
    test_unparseable_output_is_an_error()
    print("ok")
