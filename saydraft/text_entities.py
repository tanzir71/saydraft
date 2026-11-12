"""Shared patterns for literal addresses that cleanup must preserve."""

import re

# Literal dotted labels are protected broadly, including technical dotted names.
# Spoken-address conversion separately requires a recognized suffix.
BARE_DOMAIN_PATTERN = (r"(?<![\w@.-])[.-]*(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
                       r"[A-Za-z]{2,63}(?:[/?#][^\s<>\"'“”\])]+)?(?!\w)")
BARE_DOMAIN = re.compile(BARE_DOMAIN_PATTERN, re.IGNORECASE)

# These identify literal address shapes, including Unicode and local hosts;
# delivery/SMTP validity is not this module's job. The left boundary prevents
# restarting at every character of a long non-address token.
_EMAIL_LOCAL = r'''[^\s<>()\[\],;:"@]'''
_EMAIL_LABEL = r'''[^\s<>()\[\],;:"@./!?]+'''
EMAIL_PATTERN = rf"(?<!{_EMAIL_LOCAL}){_EMAIL_LOCAL}+@(?:{_EMAIL_LABEL}\.)*{_EMAIL_LABEL}"
EMAIL = re.compile(EMAIL_PATTERN, re.UNICODE)
