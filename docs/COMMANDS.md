# Commands

Every command works inside a Git repository, or with `-C <path>` on a repository
somewhere else. Global flags: `-C PATH`, `--no-color`, `--ascii`, `--version`.

Exit codes: `0` success, `1` something failed or something needs your attention,
`130` you pressed Ctrl-C.

---

## `gitctap setup`

First-time setup for a project.

What it does, in order:

1. Checks that Git exists in `PATH`.
2. Checks that the folder is a Git repository, and offers `git init` if it is not.
3. Asks for the project name (default: the folder name).
4. Asks for the clone URL on each forge, one at a time, until you answer with an empty
   line. The short name is guessed from the host and can be changed.
5. Creates a Git remote per forge, with the same name.
6. Saves the configuration to `~/.config/gitctap/projects/`.
7. Contacts every forge to confirm it is reachable and that your access works.
8. Pushes **only** after an explicit yes, and the default answer is no.

| Flag | Meaning |
| --- | --- |
| `--name NAME` | Project name, no question asked. |
| `--forge NAME=URL` | Add a forge without questions. Repeatable. A bare URL also works, and the name is guessed. |
| `--init` | Run `git init` without asking, when the folder is not a repository. |
| `--test-push` | Do the first push at the end. Passing this flag *is* the explicit confirmation. |
| `--no-push` | Never offer the first push. |
| `--no-check` | Do not contact the forges. |
| `--force` | Replace an existing configuration without asking. |
| `--timeout SEC` | Network timeout per forge (default 25). |

Non-interactive example, for a script or a fresh machine:

```sh
gitctap setup --name my-project --no-push \
  --forge github=git@github.com:me/my-project.git \
  --forge codeberg=git@codeberg.org:me/my-project.git
```

A URL that is listed twice, or a forge name that is used twice, stops setup with an
error instead of producing two remotes that fight over the same repository.

---

## `gitctap create <name> --on <forge> [--on <forge> …]`

Creates the **empty** repository on several forges in one run and links it to this folder.
This is the only command that talks to a forge API instead of to Git, because creating a
repository is the one thing Git itself cannot do.

What it does, in order:

1. resolves every `--on` value into a forge (kind + host + API base);
2. decides how each forge will authorise the request, **before** creating anything;
3. `git init` if this folder is not a repository yet (asks first, or `--init`);
4. creates the repository on each forge, one by one, reporting each separately;
5. saves the configuration, creates matching Git remotes;
6. tells you what to do with the content — and never does it for you.

```sh
gitctap create my-project --on github --on codeberg
gitctap create my-project --on github --on gitlab --public --description "one project, many forges"
gitctap create my-project --on work=gitea:git.example.org
```

### Where it can create

| `--on` value | Forge | API |
| --- | --- | --- |
| `github` | github.com | GitHub |
| `codeberg` | codeberg.org | Gitea |
| `gitea` | gitea.com | Gitea |
| `disroot` | git.disroot.org | Gitea |
| `gitlab` | gitlab.com | GitLab |
| `framagit` | framagit.org | GitLab |
| `salsa` | salsa.debian.org | GitLab |
| `name=<known>` | the same forge under another short name, e.g. `mirror=codeberg` | — |
| `name=gitea:host` | any self-hosted Gitea/Forgejo | Gitea |
| `name=gitlab:host` | any self-hosted GitLab | GitLab |
| `name=github:host` | GitHub Enterprise | GitHub |

A host without a kind is refused on purpose, with the fix in the message: gitctap does not
guess which software an unknown server runs.

### Authorisation

For each forge, in this order:

1. **A token in the environment.** `$GITCTAP_<FORGE>_TOKEN` first (the forge's short name,
   upper case), then the forge's usual variable: `$GITHUB_TOKEN`/`$GH_TOKEN`,
   `$CODEBERG_TOKEN`, `$GITEA_TOKEN`, `$GITLAB_TOKEN`/`$GL_TOKEN`.
2. **The forge's own CLI**, if it is installed and logged in: `gh`, `tea`, `glab`. gitctap
   never sees the credential in this case. `GITCTAP_DISABLE_CLI=1` turns this step off.
3. **A one-time prompt** (hidden input), only in an interactive terminal. The token is used
   for that single request and is never written anywhere.

A forge with no usable credential fails on its own line and does not stop the others.

### Flags

| Flag | Meaning |
| --- | --- |
| `--on FORGE` | Where to create it. Repeatable; the order is the order of work. |
| `--owner NAME` | Create under this organisation (GitHub/Gitea) or group (GitLab) instead of your account. |
| `--public` | Public repositories. Default is **private**, so nothing becomes visible by accident. |
| `--description TEXT` | Repository description on the forge. |
| `--https` | Store HTTPS clone URLs in the configuration instead of SSH. |
| `--init` | `git init` without asking, if this folder is not a repository yet. |
| `--push` | Push the current branch right after creating, if there are commits. |
| `--dry-run` | Show the plan and the credential source for each forge, create nothing. |
| `--timeout SEC` | Network timeout per forge, 25 seconds by default. |

### If it already exists there

The repository is **linked as it is**, marked `!` in the output, and never overwritten,
emptied or re-initialised. That is also why `create` can be run again safely: forges that
already have the repository are just linked.

### Exit codes

`0` when every forge was created or linked. `1` when at least one failed — the successful
ones are still saved into the configuration, and the failed ones are listed with a reason.

## `gitctap push`

The main command. Sends the current branch to every configured forge.

```console
$ gitctap push
gitctap! push · my-project · branch main · 3 forges
! 2 uncommitted changes stay on your disk: gitctap pushes commits only.

→ github · git@github.com:me/my-project.git
  ✓ pushed

→ codeberg · git@codeberg.org:me/my-project.git
  ✓ pushed

→ gitlab · git@gitlab.com:me/my-project.git
  ✗ rejected: the forge has commits you do not have - pull and merge, never force

result
  github   ✓
  codeberg ✓
  gitlab   ✗ rejected: the forge has commits you do not have - pull and merge, never force

! 1 of 3 forges did not accept the push: gitlab
  The forges that succeeded keep their commits. Nothing was rolled back, nothing was forced.
```

Git's own output is shown as it happens, so credential helpers and SSH passphrase
prompts still work. One forge failing never stops the others.

| Flag | Meaning |
| --- | --- |
| `--branch NAME` | Publish this branch instead of the one you are on. |
| `--tags` | Also push tags, in a second `git push --tags` per forge. Without this flag tags stay local. |
| `--only FORGE` | Only this forge. Repeatable. |
| `--skip FORGE` | Every forge except this one. Repeatable. |
| `--dry-run` | Ask Git what it would send and send nothing. |
| `--quiet` | Hide Git's output. Runs non-interactively, so it needs SSH keys or a credential helper. |
| `--set-upstream` | If the branch has no upstream yet, set it on the first forge. |

What `push` refuses to do: force anything, delete anything, mirror anything, commit
anything. A rejected push is reported and left rejected.

---

## `gitctap status`

How far each forge is from your local branch. The wording is from the forge's point of
view: "2 commits behind" means the forge is missing two of your commits.

```console
$ gitctap status
my-project · /home/me/code/my-project · branch main

github   ✓ up to date
codeberg ! 2 commits behind
gitlab   ✗ host not found - check the URL or your network
```

States: `up to date`, `N commits behind`, `N commits ahead of you (pull before you
push)`, `diverged: N behind, M ahead`, `branch <name> is not published there yet`,
`out of sync, and its commits are unknown here (git fetch to compare)`, or a reason.

Exit code is 1 when any forge is not `up to date`, which makes it usable in a
pre-flight script.

| Flag | Meaning |
| --- | --- |
| `--branch NAME` | Compare this branch. |
| `--offline` | Compare against what Git already knows locally, contact nobody. |
| `--fetch` | `git fetch` first, so counts are exact even for commits you have never seen. |
| `--timeout SEC` | Network timeout per forge. |

Without `--fetch`, gitctap asks each forge for one ref with `git ls-remote`: fast, and
it downloads no objects.

---

## `gitctap check`

Everything that could go wrong, checked before you need it. Publishes nothing.

```console
$ gitctap check
git
  ✓ git version 2.43.0 (/usr/bin/git)

repository
  ✓ /home/me/code/my-project
  ✓ branch main
  ✓ 14 commits
  ✓ working tree clean

configuration
  ✓ /home/me/.config/gitctap/projects/my-project-1a2b3c4d.json
  ✓ project my-project, 2 forges

git remotes
  github   ✓ git@github.com:me/my-project.git
  codeberg ✓ git@codeberg.org:me/my-project.git

forges
github   ✓ reachable, 3 branches
codeberg ✓ reachable, 3 branches

✓ everything is ready. gitctap push will work.
```

| Flag | Meaning |
| --- | --- |
| `--branch NAME` | Look for this branch on the forges. |
| `--offline` | Local checks only. |
| `--timeout SEC` | Network timeout per forge. |

---

## `gitctap add <name> [url]`

One more forge for this project. The URL is asked for if you leave it out.

```sh
gitctap add gitlab git@gitlab.com:me/my-project.git
gitctap add gitlab            # asks for the URL
```

The name is also the Git remote name, so it must be lower case letters, digits, dot,
dash or underscore. A duplicate name or a duplicate URL is refused. Nothing is pushed;
run `gitctap push` when you are ready.

| Flag | Meaning |
| --- | --- |
| `--no-check` | Do not contact the forge. |
| `--timeout SEC` | Network timeout. |

---

## `gitctap remove <name>`

Forgets a forge.

**This never deletes the repository on that forge**, and never deletes a branch, a tag
or a commit there. It edits the gitctap configuration, and asks separately whether the
local Git remote should go too.

| Flag | Meaning |
| --- | --- |
| `--keep-remote` | Leave the local Git remote in place, so `git push <name>` still works by hand. |
| `-y`, `--yes` | Do not ask. Also removes the local remote. |

---

## `gitctap list`

Every configured forge, its host, and whether the local Git remote matches the
configuration.

```console
$ gitctap list
my-project · /home/me/code/my-project

github   ✓ github.com      git@github.com:me/my-project.git
codeberg ✓ codeberg.org    git@codeberg.org:me/my-project.git

  2 forges · config: /home/me/.config/gitctap/projects/my-project-1a2b3c4d.json
```

A `!` in the second column means the Git remote of that name points somewhere else. In
that case gitctap pushes to the URL from its configuration and says so.
