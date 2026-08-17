# Changelog

All notable changes to gitctap! are written down here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-18

First release. One local Git project, several Git forges, one command.

### Added

- `gitctap setup` — checks Git, offers `git init`, asks for the clone URL on each
  forge, saves the configuration, creates matching Git remotes, tests reachability and
  access, and pushes only after an explicit confirmation.
- `gitctap push` — sends the current branch to every configured forge in turn, with a
  separate result line and a separate error per forge. Exit code 1 when any forge
  refused. Flags: `--branch`, `--tags`, `--only`, `--skip`, `--dry-run`, `--quiet`,
  `--set-upstream`.
- `gitctap status` — per forge: up to date, N commits behind, N commits ahead,
  diverged, not published yet, or the reason it could not be reached. Flags:
  `--branch`, `--offline`, `--fetch`, `--timeout`.
- `gitctap check` — Git, repository, branch, commits, working tree, configuration,
  remotes, reachability and authorisation, without publishing anything.
- `gitctap add <name> [url]`, `gitctap remove <name>`, `gitctap list`.
- Configuration in `~/.config/gitctap/projects/`, outside the repository, honouring
  `XDG_CONFIG_HOME` and `GITCTAP_CONFIG_DIR`, written with `0600` permissions.
- Every forge is mirrored into an ordinary Git remote of the same name, so the project
  keeps working without gitctap.
- Git's own errors are translated into one actionable line each (rejected pushes,
  missing repositories, SSH keys, credentials, unreachable hosts, timeouts).
- Any Git hosting works; GitHub, Codeberg, GitLab, Gitea, Bitbucket, SourceHut,
  Framagit, Salsa, GitFlic, GitVerse and local paths are recognised by name.
- 30 offline tests using bare repositories as forges.
- Bilingual README (English, Russian) and `docs/COMMANDS.md`, `docs/CONFIG.md`,
  `docs/SAFETY.md`.

### Deliberately absent

- Force push, in any form, behind any flag.
- `git push --mirror` and every other destructive mirroring mode.
- Deleting remote branches, tags or repositories.
- Making commits, or inventing commit messages.
- Storing tokens or any other credential.
- A GUI, issues, pull requests and CI/CD orchestration.

[0.1.0]: https://github.com/d1d2dopamine/gitctap/releases/tag/v0.1.0
