"""Pre-commit markdown checklist hook.

Fires before every Bash tool call. If the command is a git commit,
injects a checklist reminder into Claude's context — forcing a check
that all relevant markdown files were updated before the commit lands.
"""

import json
import sys


def main() -> None:
    data = json.load(sys.stdin)
    command: str = data.get("tool_input", {}).get("command", "")

    if "git commit" not in command:
        sys.exit(0)

    checklist = (
        "PRE-COMMIT MARKDOWN CHECK — confirm before committing:\n"
        "  □ ARCHITECTURE.md     — new component, pattern, or server behaviour?\n"
        "  □ DECISIONS.md        — non-obvious design choice made this step?\n"
        "  □ GLOSSARY.md         — new concept or term introduced?\n"
        "  □ QA.md               — new question answered or clarified?\n"
        "  □ MCP_SERVER.md       — any change to stock_mcp_server.py?\n"
        "  □ LEARNING_MATERIAL.md — new concept worth adding to the study guide?\n"
        "If any box applies and the file was not updated, stop and update it first."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": checklist,
        }
    }))


if __name__ == "__main__":
    main()
