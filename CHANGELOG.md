# Changelog

All notable changes to gitctap! are written down here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-18

Creating the repositories, not only publishing to them.

### Added

- `gitctap create <name> --on <forge> [--on <forge> …]` — creates the **empty** repository
  on several forges in one run, links each one as a Git remote, saves the configuration,
  and then recommends the next step for the content (`git add` / `git commit` /
  `gitctap push`) without ever doing it for you.
- Known forges for `--on`: `github`, `codeberg`, `gitea`, `disroot`, `gitlab`, `framagit`,
  `salsa`. Self-hosted servers are written out as `name=gitea:git.example.org`,
  `name=gitlab:host` or `name=github:host`; a known forge can take another short name as
  `mirror=codeberg`.
- Three ways to authorise, tried in that order: a token in the environment
  (`$GITCTAP_<FORGE>_TOKEN`, `$GITHUB_TOKEN`, `$GH_TOKEN`, `$CODEBERG_TOKEN`,
  `$GITEA_TOKEN`, `$GITLAB_TOKEN`, `$GL_TOKEN`), the forge's own CLI (`gh`, `tea`, `glab`),
  or a hidden one-time prompt. No credential is ever written anywhere.
- `create` flags: `--owner`, `--public`, `--description`, `--https`, `--init`, `--push`,
  `--dry-run`, `--timeout`. `--dry-run` also shows where each forge's credential comes from.
- `GITCTAP_DISABLE_CLI=1` to never delegate to an installed forge CLI.
- 34 more tests (64 in total), including a source-level assertion that no `DELETE`, `PUT` or
  `PATCH` request exists in the file.
- `docs/COMMANDS.md`, `docs/CONFIG.md` and `docs/SAFETY.md` sections for `create`, tokens
  and the audit of the new API client.

### Changed

- New repositories are **private** by default. `--public` is an explicit choice.
- `gitctap setup` now says that it only links repositories that already exist, and points at
  `gitctap create` for making them.

### Safety

- The forge API client sends `GET` and `POST` only, and refuses any other method before the
  request is built, so deleting or rewriting anything on a forge remains impossible.
- `auto_init` / `initialize_with_readme` are always off: the new repository is empty, so
  your first push is a plain fast-forward.
- A repository that already exists on a forge is linked as it is, never overwritten.

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

[0.2.0]: https://github.com/d1d2dopamine/gitctap/releases/tag/v0.2.0
[0.1.0]: https://github.com/d1d2dopamine/gitctap/releases/tag/v0.1.0
