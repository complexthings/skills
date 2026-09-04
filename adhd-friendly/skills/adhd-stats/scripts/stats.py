"""The arithmetic behind /adhd-stats: a scoreboard over card.log and meter.log.

Prints violation trend, reply length, card tier distribution and a modelled token saving.
The saving is arithmetic over the tier costs below, not a measurement of real usage.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import store  # noqa: E402

TURNS = 50
# ponytail: fixed per-tier costs, measure real card.md tokens if the card text ever changes size
TIER_TOKENS = {"full card": 250, "shape half": 125, "one line": 40}
FULL = TIER_TOKENS["full card"]
EMPTY = "No adhd-friendly logs yet. Run a few turns with the plugin enabled, then try again."


def _mean(xs):
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def report(cards, meters):
    """The scoreboard text for the given card.log and meter.log rows, oldest first."""
    if not cards and not meters:
        return EMPTY
    out = [f"ADHD stats: last {len(cards)} prompts, {len(meters)} scored replies.", ""]

    totals = [m.get("violations_total", 0) for m in meters]
    if totals:
        half = len(totals) // 2 or 1
        older, newer = _mean(totals[:half]), _mean(totals[half:])
        arrow = "down" if newer < older else ("up" if newer > older else "flat")
        out.append(f"Violations: {sum(totals)} total, {_mean(totals)} per reply. Trend {arrow}: {older} then {newer}.")

    words = [m.get("words", 0) for m in meters]
    if words:
        out.append(f"Reply length: {_mean(words)} words mean, {max(words)} longest.")

    if cards:
        counts = {}
        for c in cards:
            counts[c.get("mode", "unknown")] = counts.get(c.get("mode", "unknown"), 0) + 1
        out.append("Card tiers: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        saved = sum(FULL - TIER_TOKENS.get(c.get("mode"), FULL) for c in cards)
        out.append(f"Tokens saved: about {saved:,} against sending the full card every prompt.")
        out.append(f"Basis: modelled from fixed tier costs (full {FULL}, shape half "
                   f"{TIER_TOKENS['shape half']}, one line {TIER_TOKENS['one line']} tokens), not measured.")
    return "\n".join(out)


def _self_test():
    assert report([], []) == EMPTY
    cards = [{"mode": "full card"}, {"mode": "shape half"}, {"mode": "one line"}, {"mode": "one line"}]
    meters = [{"violations_total": 4, "words": 300}, {"violations_total": 0, "words": 100}]
    text = report(cards, meters)
    assert "last 4 prompts, 2 scored replies" in text, text
    assert "Violations: 4 total, 2.0 per reply. Trend down: 4.0 then 0.0." in text, text
    assert "Reply length: 200.0 words mean, 300 longest." in text, text
    assert "full card 1, one line 2, shape half 1" in text, text
    # 0 + 125 + 210 + 210
    assert "Tokens saved: about 545 " in text, text
    assert "not measured" in text
    assert "Violations" not in report(cards, [])  # cards only, no meter section
    assert "Card tiers" not in report([], meters)  # meters only, no saving claim
    print("stats.py self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(report(store.tail("card.log", TURNS), store.tail("meter.log", TURNS)))
