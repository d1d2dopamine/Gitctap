# Configuration

## Where it lives

One JSON file per project, outside the repository:

```
~/.config/gitctap/projects/<slug>-<hash>.json
```

- `<slug>` is the folder name, lower cased.
- `<hash>` is the first eight hex characters of the SHA-1 of the absolute path, so two
  projects with the same folder name never collide.
- `XDG_CONFIG_HOME` is honoured: `$XDG_CONFIG_HOME/gitctap/projects/`.
- `GITCTAP_CONFIG_DIR` overrides both, which is what the test suite uses.

The folder is created `0700` and the file `0600`. It holds names, URLs and a path, and
never a token, password or key.

Nothing is written inside your repository: a published project shows no trace of
gitctap, and the list of your mirrors is nobody else's business.

## What it looks like

```json
{
  "gitctap": 1,
  "name": "my-project",
  "path": "/home/me/code/my-project",
  "created": "2026-08-18T00:31:04Z",
  "updated": "2026-08-18T00:52:11Z",
  "forges": [
    { "name": "github", "url": "git@github.com:me/my-project.git", "remote": "github" },
    { "name": "codeberg", "url": "git@codeberg.org:me/my-project.git", "remote": "codeberg" }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `gitctap` | Configuration format version. Currently `1`. |
| `name` | Project name, used in output only. |
| `path` | Absolute path of the repository this configuration belongs to. |
| `created`, `updated` | UTC timestamps. |
| `forges[].name` | Short name, also the Git remote name. |
| `forges[].url` | Clone URL that `git push` receives. |
| `forges[].remote` | Git remote gitctap keeps in sync with that URL. |

The file is plain JSON on purpose: you can read it, diff it, back it up, and edit it in
any text editor. Writes are atomic — a temporary file plus a rename — so an
interrupted `gitctap add` cannot leave half a configuration behind.

## The configuration is the source of truth

Every forge is also mirrored into an ordinary Git remote with the same name, which
means the project keeps working with plain Git:

```sh
git push codeberg main     # works without gitctap
git fetch github
```

But the configuration wins. Before each push gitctap compares the remote's URL with
the configured one:

- they match → it pushes through the remote name;
- they differ, or the remote is gone → it pushes to the configured URL and tells you
  about the mismatch, instead of quietly using an address you did not choose.

`gitctap check` and `gitctap list` show the same comparison, so a hand-edited remote is
visible before it matters.

## Authorisation is Git's job

gitctap never asks for, stores or transmits credentials. Access comes from whatever
Git already uses:

- SSH keys and `ssh-agent` for `git@host:owner/repo.git` URLs;
- a credential helper for HTTPS URLs, for example `git config --global credential.helper`.

During `push`, Git's own output stays on screen, so a passphrase or helper prompt
appears where you can answer it. Read-only calls (`status`, `check`, the reachability
step of `setup` and `add`) run with `GIT_TERMINAL_PROMPT=0`, `ssh -o BatchMode=yes` and
a timeout, so they fail with a clear line instead of blocking forever.

`push --quiet` is also non-interactive, which makes it the flag for cron and CI, where
SSH keys or a helper must already be in place.

## Tokens for `gitctap create`

`gitctap create` is the only command that needs a forge credential, and it never stores
one. Nothing about tokens is written into the configuration file, into the repository, or
into any cache.

For each forge it looks, in this order, at:

| Source | Example |
| --- | --- |
| `$GITCTAP_<FORGE>_TOKEN` — the forge's short name, upper case, non-letters as `_` | `GITCTAP_WORK_TOKEN`, `GITCTAP_MIRROR_TOKEN` |
| the forge's own usual variable | `GITHUB_TOKEN`, `GH_TOKEN`, `CODEBERG_TOKEN`, `GITEA_TOKEN`, `GITLAB_TOKEN`, `GL_TOKEN` |
| the forge's official CLI, already logged in | `gh`, `tea`, `glab` |
| a hidden one-time prompt, interactive terminals only | typed once, used once |

A forge added under another short name keeps its own variable too: `--on mirror=codeberg`
accepts `$GITCTAP_MIRROR_TOKEN`, `$CODEBERG_TOKEN` and `$GITEA_TOKEN`.

Scopes to ask for when you create the token: `repo` on GitHub, `write:repository` on
Gitea/Codeberg/Forgejo, `api` on GitLab.

A sensible place for them is your shell profile, or better, a password manager that exports
them for one shell session:

```sh
export GITHUB_TOKEN="..."
export CODEBERG_TOKEN="..."
```

| Variable | Effect |
| --- | --- |
| `GITCTAP_DISABLE_CLI=1` | Never delegate to `gh`/`tea`/`glab`, even if they are installed. Useful in CI, and in the test suite. |

Pushing itself needs no token at all: that is Git's own authorisation, as described below.

## Moving or renaming a project

The configuration is found by the repository's absolute path. If you rename or move the
folder, gitctap looks for a configuration whose stored `path` still matches, and if
there is none it says there is no configuration yet. Either run `gitctap setup` again —
it takes seconds — or edit `path` in the JSON file and rename the file to match the new
folder name.

## Several projects, several machines

One configuration file per repository, so nothing is shared and nothing is global. To
carry a setup to another machine, copy the JSON file and fix `path` inside it, or just
run `gitctap setup` there with `--forge` flags:

```sh
gitctap setup --no-push \
  --forge github=git@github.com:me/my-project.git \
  --forge codeberg=git@codeberg.org:me/my-project.git
```

## Forge names

The name is guessed from the host: `github.com` → `github`, `codeberg.org` →
`codeberg`, `git.sr.ht` → `sourcehut`, `git.example.org` → `example`. GitHub, Codeberg,
GitLab, Gitea, Bitbucket, SourceHut, Framagit, Salsa, GitFlic, GitVerse and Disroot are
recognised by name, but nothing is special-cased in behaviour: any Git hosting works,
including one you host yourself, and including a bare repository on a local path or a
USB drive.
