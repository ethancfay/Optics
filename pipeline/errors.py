"""Shared error type for every pipeline stage (design § Error model).

Messages must contain only URLs, page numbers, counts, field names,
identifiers and timestamps. Never put response body text or a record's
repr() in a message (Req 3.3).
"""


class PipelineError(Exception):
    """A defined pipeline failure. `__main__` prints the message to stderr and exits 1 (Req 14.8)."""


class ConfigError(PipelineError):
    """A Rules_Config failure (condition-grouping Req 2.7, 2.9).

    `lines` holds one message per failed check; `__main__` prints one
    `error:` line per entry. A single string becomes a one-line list.
    """

    def __init__(self, lines: "list[str] | str") -> None:
        self.lines: list[str] = [lines] if isinstance(lines, str) else list(lines)
        super().__init__("\n".join(self.lines))
