#!/usr/bin/env python3
"""Every shipped avatar SVG fits the Desktop `Svg` source cap.

The mod API rejects an `Svg` source over 131072 chars, and one rejected avatar
blanks the whole band (#155), so export.mjs writes one SVG per frame. Fails if
any `hooks/assets/avatars/*.svg` is over the cap, or if a manifest entry is
missing one of its `<name>_<i>.svg` frames.

Run: python3 test_svg_cap.py
"""
import json
from pathlib import Path

CAP = 131072
ASSETS = Path(__file__).resolve().parents[2] / "hooks" / "assets" / "avatars"


def test_svg_cap():
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    missing = [f"{name}_{i}.svg" for name, entry in manifest.items() for i in range(entry["frames"])
               if not (ASSETS / f"{name}_{i}.svg").exists()]
    assert not missing, f"missing frame SVGs: {missing[:5]}"
    over = {p.name: len(p.read_text()) for p in ASSETS.glob("*.svg") if len(p.read_text()) > CAP}
    assert not over, f"SVGs over {CAP} chars: {over}"


if __name__ == "__main__":
    test_svg_cap()
    print("ok")
