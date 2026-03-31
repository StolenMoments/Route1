CLI_CONFIGS = {
    "claude": {
        "command": "claude",
        "auto_approve": False,
        "approval_patterns": [
            r"\(y/n\)",
            r"Continue\?",
            r"Proceed\?",
            r"Are you sure",
        ],
    },
    "gemini": {
        "command": "gemini",
        "auto_approve": False,
        "approval_patterns": [
            r"\(y/n\)",
            r"Continue\?",
            r"Proceed\?",
        ],
    },
    "codex": {
        "command": "codex",
        "auto_approve": False,
        "approval_patterns": [
            r"\(y/n\)",
            r"Continue\?",
            r"Proceed\?",
        ],
    },
}

DEFAULT_CWD = "~"
HOST = "127.0.0.1"
PORT = 8000
