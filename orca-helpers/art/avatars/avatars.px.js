// All six Agent Harness avatars. Build and export with: node export.mjs
include("base.px.js")
for (const id of ["claude", "copilot", "opencode", "codex", "pi", "antigravity"]) include(`harnesses/${id}.px.js`)
