# Security policy

Please report vulnerabilities privately through GitHub's "Report a vulnerability" button
(Security tab) instead of a public issue.

Notes for users: API keys and the OpenSubtitles password are stored in `config.json` on your own PC in plain
text (`%APPDATA%\SubGrab`, or the `data` folder in portable mode). SubGrab sends no telemetry; it only talks to
the subtitle sites you enable, IMDb's public suggestion endpoint (posters/details) and GitHub (update check).
