# Safety

The rule the whole tool is built around:

> **gitctap never deletes anything on a forge, and never rewrites its history, just
> because your local folder looks different.**

A multi-forge tool is dangerous in exactly one way: it is tempting to implement
"publish everywhere" as "make the other side identical to me". That is
`git push --mirror`, and it moves and deletes refs on the remote. gitctap does the
opposite — it only ever adds commits to a branch on a forge, through a plain
`git push`, and reports whatever Git says.

## What is not implemented

These are absent from the code, not merely disabled:

| Never | Why |
| --- | --- |
| `git push --force`, `--force-with-lease` | Overwrites commits that exist only on the forge. A rejected push is information, not an obstacle. |
| `git push --mirror`, `--prune` | Deletes remote refs that are missing locally. |
| `git push <remote> :branch` (delete refspec) | Deletes a remote branch. |
| Deleting remote tags | Same, for tags. |
| Deleting a remote repository | gitctap has no forge API client at all. |
| Creating a remote repository | Same reason. You create the empty repository on the forge yourself. |
| `git commit`, `git add`, generated commit messages | Publishing and authoring are different jobs. |
| `git reset`, `git rebase`, `git filter-branch` | gitctap does not touch your history either. |
| Storing tokens, passwords or keys | Authorisation belongs to Git and to your SSH agent. |

What is actually run against a forge is a short list: `git push <target>
refs/heads/<branch>:refs/heads/<branch>`, `git push <target> --tags` with `--tags`,
`git ls-remote`, and `git fetch` with `status --fetch`. Nothing else.

## Rejected pushes stay rejected

When the forge has commits you do not have, Git refuses. gitctap prints:

```
✗ rejected: the forge has commits you do not have - pull and merge, never force
```

and moves on to the next forge. It does not retry, does not escalate, does not offer a
force flag. The fix is yours:

```sh
git pull --rebase github main
gitctap push
```

## Partial failure is honest

Forges are walked one at a time, and one failure never stops the walk. The ones that
accepted the push keep their commits — there is no rollback, because rolling back means
rewriting history on a forge that did nothing wrong. The summary lists every forge, the
failures are listed again at the bottom, and the exit code is 1 so a script notices:

```sh
gitctap push || echo "at least one forge is behind; check gitctap status"
```

`gitctap status` is the way to find out later which forge is behind, and repeating
`gitctap push` sends only what is missing, because that is Git's own logic.

## `remove` is not a delete

`gitctap remove codeberg` takes a forge out of the gitctap configuration. On the forge,
the repository, its branches, its tags and its commits are untouched — gitctap cannot
touch them, having no API client. The only extra question is whether the *local* Git
remote should go too, and `--keep-remote` keeps it so `git push codeberg main` still
works by hand.

The test suite asserts this: after `remove`, the bare repository used as a forge still
exists and still points at the same commit.

## Nothing hangs, nothing prompts invisibly

- Read-only network calls (`status`, `check`, the reachability step of `setup` and
  `add`) run with `GIT_TERMINAL_PROMPT=0`, `ssh -o BatchMode=yes` and a timeout
  (`--timeout`, 25 seconds by default). They fail with one clear line instead of
  waiting for input nobody typed.
- `push` shows Git's own output, so a passphrase or credential prompt appears where you
  can answer it. `push --quiet` is the non-interactive variant, for cron and CI.
- `GIT_OPTIONAL_LOCKS=0` is set, so gitctap never fights another Git process for the
  index lock.

## Your own protections still apply

gitctap adds nothing to your repository and changes no Git setting, so branch
protection rules, server-side hooks, required reviews and signed commits behave exactly
as they do with plain `git push`. When a forge refuses because of one of them, the
reason is shown under that forge's name.

## Read it yourself

The whole tool is one Python file with no dependencies. The forge-facing part is small
enough to audit in a few minutes:

```sh
grep -n '"push"\|ls-remote\|fetch' gitctap.py
```

If you find a command in there that can destroy something on a forge, that is a bug —
please open an issue.
