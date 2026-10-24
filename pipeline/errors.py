"""Shared error type for every pipeline stage (design § Error model).

Messages must contain only URLs, page numbers, counts, field names,
identifiers and timestamps. Never put response body text or a record's
repr() in a message (Req 3.3).
"""


class PipelineError(Exception):
    """A defined pipeline failure. `__main__` prints the message to stderr and exits 1 (Req 14.8)."""
