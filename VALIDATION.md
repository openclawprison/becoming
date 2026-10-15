# Validation

2026-10-15: 19 automated tests passed on Python 3.14. All tests use the standard library and controlled fixtures; they do not depend on live websites.

A separate live test started the observer at http://127.0.0.1:8890 and supplied only https://www.python.org/ as an initial location. The agent read that page and autonomously followed links to Swiss Python Summit 2026 and PyCon Panamá 2026. The observer displayed fetched content, the actual chosen URLs, decision scores and learning updates. This is evidence of working public-page exploration, not evidence of semantic understanding or human cognition. Test browsing memory is excluded from the repository.

Checks include initially empty memory/identity, experience-driven preference changes, reduced novelty on repeated text, full RNG continuation after saving, bounded retention, malicious source text staying inert, HTTP-only URL validation, private/mixed DNS denial, robots denials and failures, redirect destination checks, compressed-page expansion limits, non-text rejection, extracted link following, invalid observer controls, and Host/Origin checks.

GitHub Actions runs the same suite on Python 3.11 and 3.14. Live sites may change, refuse bots, require JavaScript or block requests. The supported experience is a sanitized text reader, not unrestricted interactive browser automation. The no-biography constraint is verified as data state, not as a subjective belief.
