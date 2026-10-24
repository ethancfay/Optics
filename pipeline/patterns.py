"""Email_Pattern and Phone_Pattern, shared by the Contact_Scrubber and the PII_Guard.

Defined once here so that the location text redaction (Req 3.2) and the final
output check (Req 8.1) use exactly the same patterns.
"""
import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# The (?<![\d.]) lookbehind stops the decimal part of a long coordinate such
# as -71.8123456789 from matching (design § PII_Guard).
PHONE = re.compile(
    r"(?<![\d.])(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?!\d)"
)
PATTERNS = (("email", EMAIL), ("phone", PHONE))
