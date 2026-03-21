"""Post-commit next step explanation hook.

Fires after every Bash tool call. If the command was a git commit,
injects an instruction for Claude to automatically explain what the
next protocol step will build — without the user having to ask.
"""

import json
import sys


def main() -> None:
    data = json.load(sys.stdin)
    command: str = data.get("tool_input", {}).get("command", "")

    if "git commit" not in command:
        sys.exit(0)

    message = (
        "Commit successful. "
        "Use the get_current_step MCP tool to check the next step, "
        "then concisely explain what you will build in that step "
        "before asking Eran for permission to proceed."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }))


if __name__ == "__main__":
    main()
