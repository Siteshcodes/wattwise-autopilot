# GitHub version control setup

Prepared 13 October 2026 for the existing WattWise project.

- Local Git repository initialized with branch `main`.
- Remote `origin`: `https://github.com/Siteshcodes/wattwise-autopilot.git`.
- Initial commit message: `feat: initial WattWise V1 foundation`.
- Original source files and local runtime data were preserved. `.gitignore` was
  extended, and license/attribution documentation was added.
- Python environments, dependency installs, caches, Next.js generated files,
  build outputs, SQLite files and journals, environment files and credential
  containers are excluded. The reviewed `.env.example` stays in source control.

## Secret scan

Before staging, all 39 first-party files then present were scanned, including
ignored local databases and generated first-party files. Installed dependency
trees, build outputs, Git internals and caches were excluded. There were no
previously tracked files. The staged file contents were separately scanned
before commit.

The scan checked AWS access-key IDs and secret-key assignments, common provider
and GitHub token formats, Slack tokens, JWTs, private-key headers, credentials
embedded in URLs and literal secret/password assignments. It reported file paths,
line numbers and rule names only, never matched values. No secret patterns were
detected. Pattern scanning cannot prove that arbitrary secrets are absent.

See [third-party notices](../THIRD_PARTY_NOTICES.md) for the dependency license
inventory, preservation of upstream notices and distribution-specific limits.

## Connect and push

The remote is already configured. Inspect it and push from the project root:

```powershell
cd D:\8.Hackthon\WattWise
git status
git remote -v
git push -u origin main
```

If you later need to change this remote URL:

```powershell
git remote set-url origin https://github.com/Siteshcodes/wattwise-autopilot.git
```

Authenticate through GitHub/Git Credential Manager when Git requests it. Keep
credentials out of the remote URL and project files. No remote writes were
performed during setup. If Git rejects the push because the remote already has
commits, fetch and inspect its history before reconciling it; do not force-push.
