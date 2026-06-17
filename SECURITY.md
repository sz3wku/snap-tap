# Security Policy

`snap-tap` controls real phones. Treat security issues as safety issues too:
unexpected phone touches, leaked screen data, leaked typed text, unsafe
artifact paths, and stale target replay are all security-relevant.

## Supported Versions

`snap-tap` is pre-alpha. Until the first public alpha tag, only the current
default branch is supported.

After public releases begin, this section will list supported release lines.

## Reporting a Vulnerability

Do not open a public issue for a vulnerability.

Use GitHub Private Vulnerability Reporting on the public repository. If that
channel is temporarily unavailable, open a minimal public issue asking for a
private security contact and do not include technical details.

Include:

- affected commit or version,
- operating system and Python version,
- device platform and setup state,
- exact command or API call,
- expected behavior,
- observed behavior,
- whether a phone touch, screenshot, typed text, or artifact path was exposed.

Avoid sharing raw screenshots, raw XML, typed private text, tokens, account
data, or full local paths unless they are strictly required to prove the issue.

## Scope

Security reports are welcome for:

- phone-touch operations that bypass primitive receipts,
- stale target replay that can touch the wrong element,
- raw coordinate or selector authority exposed as public API,
- leaked screenshot bytes, raw XML, typed text, selectors, private paths, or
  tokens,
- unsafe artifact path handling,
- dependency confusion or package publishing risks,
- CI or release workflow weaknesses.

Out of scope:

- unsupported local modifications,
- devices already compromised outside `snap-tap`,
- social platform account policy issues,
- external product runtime issues unless they are reproducible in standalone
  `snap-tap`.

## Handling

The maintainer will acknowledge valid reports privately, keep reproduction data
minimal, and prefer small fixes with focused tests. Public disclosure should
wait until a fix is available or a coordinated disclosure date is agreed.
