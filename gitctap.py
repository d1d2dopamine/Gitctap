#!/usr/bin/env python3
"""gitctap! - one local Git project, several Git forges, one command.

gitctap does not replace Git and it never invents its own way to compare files.
Git already knows how to talk to several remotes and how to send exactly the
commits that are missing on the other side. gitctap only keeps the list of
forges, walks it, and reports every forge separately.

MIT licensed. Python 3.8+, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "0.1.0"
CONFIG_VERSION = 1
DEFAULT_TIMEOUT = 25

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# Hosts we can name on our own. Anything else still works: gitctap asks for a
# short name and treats every forge exactly the same way.
KNOWN_FORGES = {
    "github.com": "github",
    "codeberg.org": "codeberg",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "git.sr.ht": "sourcehut",
    "gitea.com": "gitea",
    "framagit.org": "framagit",
    "salsa.debian.org": "salsa",
    "invent.kde.org": "kde",
    "gitflic.ru": "gitflic",
    "gitverse.ru": "gitverse",
    "git.disroot.org": "disroot",
}

# Git's own wording -> one short line a human can act on.
ERROR_HINTS: Sequence[Tuple[str, str]] = (
    ("could not resolve host", "host not found - check the URL or your network"),
    ("name or service not known", "host not found - check the URL or your network"),
    ("network is unreachable", "network unreachable"),
    ("connection refused", "connection refused by the host"),
    ("connection timed out", "connection timed out"),
    ("operation timed out", "connection timed out"),
    ("timed out", "connection timed out"),
    ("permission denied (publickey", "SSH key rejected - add your key to this forge or run ssh-add"),
    ("host key verification failed", "unknown SSH host key - connect once with ssh to accept it"),
    ("authentication failed", "authentication failed - check your token or credential helper"),
    ("could not read username", "credentials required - use SSH or set up a credential helper"),
    ("terminal prompts disabled", "credentials required - use SSH or set up a credential helper"),
    ("invalid username or token", "authentication failed - check your token"),
    ("repository not found", "repository not found - create it on the forge first"),
    ("does not appear to be a git repository", "no Git repository at that URL"),
    ("remote: access denied", "access denied for this account"),
    ("the requested url returned error: 403", "access denied (HTTP 403)"),
    ("the requested url returned error: 404", "not found (HTTP 404) - check the URL"),
    ("non-fast-forward", "rejected: the forge has commits you do not have - pull and merge, never force"),
    ("fetch first", "rejected: the forge has commits you do not have - pull and merge, never force"),
    ("protected branch", "rejected by a branch protection rule on the forge"),
    ("pre-receive hook declined", "rejected by a hook on the forge"),
    ("shallow update not allowed", "rejected: a shallow clone cannot be pushed"),
    ("unable to access", "cannot reach the forge over HTTP(S)"),
)


# --------------------------------------------------------------------------- #
# terminal
# --------------------------------------------------------------------------- #


class Term:
    """Colours and symbols, both switchable off."""

    def __init__(self, color: bool = False, unicode_ok: bool = False) -> None:
        self.color = color
        self.unicode = unicode_ok

    def paint(self, text: str, code: str) -> str:
        if not self.color:
            return text
        return "\033[%sm%s\033[0m" % (code, text)

    def bold(self, text: str) -> str:
        return self.paint(text, "1")

    def dim(self, text: str) -> str:
        return self.paint(text, "2")

    def green(self, text: str) -> str:
        return self.paint(text, "32")

    def red(self, text: str) -> str:
        return self.paint(text, "31")

    def yellow(self, text: str) -> str:
        return self.paint(text, "33")

    def cyan(self, text: str) -> str:
        return self.paint(text, "36")

    @property
    def ok(self) -> str:
        return self.green("\u2713" if self.unicode else "+")

    @property
    def bad(self) -> str:
        return self.red("\u2717" if self.unicode else "x")

    @property
    def alert(self) -> str:
        return self.yellow("!")

    @property
    def arrow(self) -> str:
        return self.cyan("\u2192" if self.unicode else ">")

    @property
    def dot(self) -> str:
        return "\u00b7" if self.unicode else "-"


TERM = Term()


def detect_color(force_off: bool) -> bool:
    if force_off or os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("GITCTAP_FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def detect_unicode(force_off: bool) -> bool:
    if force_off:
        return False
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in encoding


def out(message: str = "") -> None:
    print(message)


def eout(message: str = "") -> None:
    print(message, file=sys.stderr)


def note(message: str) -> None:
    out("  " + TERM.dim(message))


def die(message: str, code: int = 1) -> "None":
    eout("%s %s" % (TERM.bad, message))
    raise SystemExit(code)


def interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except ValueError:  # pragma: no cover - closed stdin
        return False


def ask(prompt: str, default: Optional[str] = None) -> str:
    if not interactive():
        die("%s: nothing to read from, this is not an interactive terminal (pass the value as a flag)" % prompt)
    suffix = " [%s]" % default if default else ""
    try:
        raw = input("%s %s%s: " % (TERM.bold("?"), prompt, suffix)).strip()
    except (EOFError, KeyboardInterrupt):
        out()
        die("aborted, nothing was changed", 130)
        return ""
    return raw or (default or "")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    if not interactive():
        return default
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            raw = input("%s %s %s " % (TERM.bold("?"), prompt, suffix)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            out()
            die("aborted, nothing was changed", 130)
            return False
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        out("  please answer y or n")


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #


def git_binary() -> str:
    found = shutil.which("git")
    if not found:
        die("git is not installed, or not in PATH. gitctap is a wrapper around Git: install Git first.")
    return str(found)


def run_git(
    args: Sequence[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    network: bool = False,
) -> Tuple[int, str, str]:
    """Run git and capture its output. Never asks the user anything."""
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    if network:
        # Read-only network calls must fail instead of blocking on a prompt.
        env["GIT_TERMINAL_PROMPT"] = "0"
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    try:
        done = subprocess.run(
            [git_binary(), *args],
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "", "connection timed out"
    return (
        done.returncode,
        done.stdout.decode("utf-8", "replace").strip(),
        done.stderr.decode("utf-8", "replace").strip(),
    )


def stream_git(args: Sequence[str], cwd: Optional[Path] = None) -> int:
    """Run git with its own output on screen, so credential prompts still work."""
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    done = subprocess.run([git_binary(), *args], cwd=str(cwd) if cwd else None, env=env)
    return done.returncode


def explain(text: str) -> str:
    low = (text or "").lower()
    for needle, hint in ERROR_HINTS:
        if needle in low:
            return hint
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line:
            return line[:160]
    return "failed for an unknown reason"


def find_repo_root(start: Path) -> Optional[Path]:
    code, stdout, _ = run_git(["rev-parse", "--show-toplevel"], cwd=start)
    if code != 0 or not stdout:
        return None
    return Path(stdout)


def current_branch(root: Path) -> Optional[str]:
    code, stdout, _ = run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=root)
    if code != 0 or not stdout:
        return None
    return stdout


def has_commits(root: Path) -> bool:
    code, _, _ = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=root)
    return code == 0


def dirty_files(root: Path) -> List[str]:
    code, stdout, _ = run_git(["status", "--porcelain"], cwd=root)
    if code != 0:
        return []
    return [line for line in stdout.splitlines() if line.strip()]


def rev_parse(root: Path, ref: str) -> Optional[str]:
    code, stdout, _ = run_git(["rev-parse", "--verify", "--quiet", ref], cwd=root)
    if code != 0 or not stdout:
        return None
    return stdout


def commit_exists(root: Path, sha: str) -> bool:
    code, _, _ = run_git(["cat-file", "-e", "%s^{commit}" % sha], cwd=root)
    return code == 0


def list_remotes(root: Path) -> Dict[str, str]:
    code, stdout, _ = run_git(["config", "--get-regexp", r"^remote\..*\.url$"], cwd=root)
    if code != 0:
        return {}
    found: Dict[str, str] = {}
    for line in stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        key, url = parts
        pieces = key.split(".")
        if len(pieces) >= 3:
            found[".".join(pieces[1:-1])] = url.strip()
    return found


def set_remote(root: Path, name: str, url: str) -> Tuple[bool, str]:
    """Create the remote, or point an existing one at this URL."""
    existing = list_remotes(root).get(name)
    if existing is None:
        code, _, stderr = run_git(["remote", "add", name, url], cwd=root)
        return code == 0, stderr
    if existing == url:
        return True, ""
    code, _, stderr = run_git(["remote", "set-url", name, url], cwd=root)
    return code == 0, stderr


def ls_remote(url: str, branch: Optional[str], root: Optional[Path], timeout: int) -> Tuple[int, str, str]:
    args = ["ls-remote", "--heads", url]
    if branch:
        args.append("refs/heads/%s" % branch)
    return run_git(args, cwd=root, timeout=timeout, network=True)


# --------------------------------------------------------------------------- #
# urls
# --------------------------------------------------------------------------- #


WEB_PATH_RE = re.compile(r"/(tree|blob|commits?|src|branch|-/tree|releases|issues|pulls?)(/|$)")


def normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise ValueError("the URL is empty")
    if any(ch.isspace() for ch in url):
        raise ValueError("the URL contains whitespace")
    if url.startswith("~"):
        url = os.path.expanduser(url)
    while url.endswith("/"):
        url = url[:-1]
    if not url:
        raise ValueError("the URL is empty")
    return url


def url_host(url: str) -> Optional[str]:
    scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*://(?:[^/@]*@)?([^/:]+)", url)
    if scheme:
        return scheme.group(1).lower()
    if url.startswith("/") or url.startswith("."):
        return None
    scp = re.match(r"^(?:[^@/]+@)?([^:/]+):", url)
    if scp:
        return scp.group(1).lower()
    return None


def guess_forge_name(url: str) -> str:
    host = url_host(url)
    if not host:
        return "local"
    if host in KNOWN_FORGES:
        return KNOWN_FORGES[host]
    for known, name in KNOWN_FORGES.items():
        if host.endswith("." + known):
            return name
    labels = [part for part in host.split(".") if part]
    if not labels:
        return "forge"
    skip = {"git", "www", "code", "scm", "repo", "src"}
    for label in labels:
        if label not in skip:
            return slugify(label) or "forge"
    return slugify(labels[0]) or "forge"


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", (text or "").strip().lower()).strip("-.")
    return value


def check_forge_name(name: str) -> str:
    value = (name or "").strip().lower()
    if not NAME_RE.match(value):
        raise ValueError(
            "forge name %r is not usable as a Git remote name (use letters, digits, dot, dash, underscore)" % name
        )
    return value


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #


def config_home() -> Path:
    override = os.environ.get("GITCTAP_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / "gitctap"
    return Path.home() / ".config" / "gitctap"


def projects_dir() -> Path:
    return config_home() / "projects"


def config_path_for(root: Path) -> Path:
    resolved = str(root.resolve())
    key = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:8]
    slug = slugify(root.name) or "project"
    return projects_dir() / ("%s-%s.json" % (slug, key))


def load_config(root: Path) -> Optional[dict]:
    primary = config_path_for(root)
    if primary.is_file():
        return read_config_file(primary)
    # The folder may have been renamed: fall back to a scan by stored path.
    resolved = str(root.resolve())
    directory = projects_dir()
    if directory.is_dir():
        for candidate in sorted(directory.glob("*.json")):
            data = read_config_file(candidate, quiet=True)
            if data and data.get("path") == resolved:
                return data
    return None


def read_config_file(path: Path, quiet: bool = False) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        if quiet:
            return None
        die("cannot read the configuration at %s: %s" % (path, problem))
        return None
    if not isinstance(data, dict):
        if quiet:
            return None
        die("the configuration at %s is not a gitctap configuration" % path)
        return None
    data["_path"] = str(path)
    forges = data.get("forges")
    if not isinstance(forges, list):
        data["forges"] = []
    return data


def save_config(root: Path, config: dict) -> Path:
    path = Path(config.get("_path") or config_path_for(root))
    payload = {
        "gitctap": CONFIG_VERSION,
        "name": config.get("name") or root.name,
        "path": str(root.resolve()),
        "created": config.get("created") or now_iso(),
        "updated": now_iso(),
        "forges": [
            {"name": forge["name"], "url": forge["url"], "remote": forge.get("remote") or forge["name"]}
            for forge in config.get("forges", [])
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(config_home()), 0o700)
        os.chmod(str(path.parent), 0o700)
    except OSError:
        pass
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass
    config["_path"] = str(path)
    return path


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_repo(args: argparse.Namespace) -> Path:
    start = Path(args.chdir).expanduser() if args.chdir else Path.cwd()
    if not start.is_dir():
        die("%s is not a directory" % start)
    root = find_repo_root(start)
    if root is None:
        die("%s is not inside a Git repository. Run: git init, then gitctap setup" % start)
        raise SystemExit(1)
    return root


def require_config(root: Path) -> dict:
    config = load_config(root)
    if config is None:
        die("no gitctap configuration for %s yet. Run: gitctap setup" % root)
        raise SystemExit(1)
    if not config.get("forges"):
        die("the configuration has no forges. Run: gitctap add <name> <url>")
    return config


def select_forges(config: dict, only: Sequence[str], skip: Sequence[str]) -> List[dict]:
    forges = list(config.get("forges", []))
    wanted = {name.strip().lower() for name in only or []}
    unwanted = {name.strip().lower() for name in skip or []}
    known = {forge["name"] for forge in forges}
    for name in wanted | unwanted:
        if name not in known:
            die("unknown forge %r. Configured: %s" % (name, ", ".join(sorted(known)) or "none"))
    if wanted:
        forges = [forge for forge in forges if forge["name"] in wanted]
    if unwanted:
        forges = [forge for forge in forges if forge["name"] not in unwanted]
    if not forges:
        die("no forges left to work with after --only/--skip")
    return forges


def push_target(root: Path, forge: dict) -> str:
    """Push through the remote name when it matches, otherwise through the URL.

    This keeps gitctap honest: the config is the source of truth, and a remote
    that someone edited by hand is never silently used instead of it.
    """
    remote = forge.get("remote") or forge["name"]
    if list_remotes(root).get(remote) == forge["url"]:
        return remote
    return forge["url"]


def column_width(forges: Sequence[dict]) -> int:
    return max([len(forge["name"]) for forge in forges] + [4])


def resolve_branch(root: Path, requested: Optional[str]) -> str:
    if requested:
        return requested
    branch = current_branch(root)
    if branch is None:
        die(
            "HEAD is detached, so there is no branch to publish. "
            "Check out a branch (git switch -c <name>) or pass --branch <name>"
        )
        raise SystemExit(1)
    return branch


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #


def parse_forge_flag(value: str) -> Tuple[Optional[str], str]:
    if "=" in value:
        name, _, url = value.partition("=")
        return name.strip().lower() or None, url.strip()
    return None, value.strip()


def cmd_setup(args: argparse.Namespace) -> int:
    start = Path(args.chdir).expanduser() if args.chdir else Path.cwd()
    if not start.is_dir():
        die("%s is not a directory" % start)
    git_binary()

    root = find_repo_root(start)
    if root is None:
        out("%s %s is not a Git repository yet." % (TERM.alert, start))
        create = args.init or ask_yes_no("Create a Git repository here?", default=True)
        if not create:
            die("nothing to publish without a Git repository. Run: git init")
        code, _, stderr = run_git(["init"], cwd=start)
        if code != 0:
            die("git init failed: %s" % explain(stderr))
        root = find_repo_root(start)
        if root is None:
            die("git init reported success but the repository is not there")
            return 1
        out("%s created a Git repository in %s" % (TERM.ok, root))

    existing = load_config(root)
    if existing and not args.force:
        out("%s this project already has a gitctap configuration:" % TERM.alert)
        print_forges(existing)
        if not ask_yes_no("Replace it? (the remote repositories are not touched)", default=False):
            note("kept as it is. Use gitctap add / gitctap remove to change single forges.")
            return 0

    if args.name:
        name = args.name
    elif interactive():
        name = ask("Project name", default=root.name)
    else:
        name = root.name
    forges: List[dict] = []
    seen_names: Dict[str, str] = {}
    seen_urls: Dict[str, str] = {}

    def remember(forge_name: Optional[str], raw_url: str) -> None:
        try:
            url = normalize_url(raw_url)
        except ValueError as problem:
            die(str(problem))
            return
        chosen = forge_name or guess_forge_name(url)
        if not forge_name and interactive():
            chosen = ask("Short name for this forge", default=chosen)
        try:
            chosen = check_forge_name(chosen)
        except ValueError as problem:
            die(str(problem))
            return
        if chosen in seen_names:
            die("forge name %r is used twice" % chosen)
        if url in seen_urls:
            die("the URL %s is listed twice (as %s and again now)" % (url, seen_urls[url]))
        if WEB_PATH_RE.search(url):
            out("%s %s looks like a page in the web interface, not a clone URL" % (TERM.alert, url))
        seen_names[chosen] = url
        seen_urls[url] = chosen
        forges.append({"name": chosen, "url": url, "remote": chosen})

    if args.forge:
        for entry in args.forge:
            flag_name, flag_url = parse_forge_flag(entry)
            if not flag_url:
                die("--forge needs a URL, got %r" % entry)
            remember(flag_name, flag_url)
    else:
        out()
        out("Add the repositories you already created on each forge.")
        note("gitctap never creates or deletes anything on a forge. Make the empty repository there first.")
        note("Paste a clone URL (SSH or HTTPS). Press Enter on an empty line when you are done.")
        out()
        while True:
            raw = ask("Repository URL #%d (empty to finish)" % (len(forges) + 1))
            if not raw:
                break
            remember(None, raw)

    if not forges:
        die("no forges given, so there is nothing to save")

    config = {"name": name, "forges": forges, "created": (existing or {}).get("created")}
    if existing:
        config["_path"] = existing.get("_path")

    out()
    for forge in forges:
        good, stderr = set_remote(root, forge["remote"], forge["url"])
        if good:
            out("%s git remote %s %s %s" % (TERM.ok, TERM.bold(forge["remote"]), TERM.dot, forge["url"]))
        else:
            out("%s could not set the git remote %s: %s" % (TERM.alert, forge["remote"], explain(stderr)))
            note("gitctap will push to the URL directly instead.")

    path = save_config(root, config)
    out("%s configuration saved to %s" % (TERM.ok, path))

    if not args.no_check:
        out()
        out(TERM.bold("reachability"))
        failures = check_reachability(root, forges, None, args.timeout)
        if failures:
            note("fix the failing forges and run gitctap check again.")

    if not has_commits(root):
        out()
        out("%s this repository has no commits yet, so there is nothing to push." % TERM.alert)
        note("Make your first commit yourself: git add . && git commit -m \"first commit\"")
        note("Then run: gitctap push")
        return 0

    branch = current_branch(root) or "HEAD"
    out()
    do_push = args.test_push
    if not do_push and not args.no_push:
        do_push = ask_yes_no(
            "Push branch %s to all %d forges now?" % (branch, len(forges)),
            default=False,
        )
    if not do_push:
        note("No push was made. When you want one, run: gitctap push")
        return 0

    return do_pushes(root, forges, branch, tags=False, dry_run=False, quiet=False, set_upstream=False)


def cmd_push(args: argparse.Namespace) -> int:
    root = require_repo(args)
    config = require_config(root)
    forges = select_forges(config, args.only, args.skip)

    if not has_commits(root):
        die(
            "this repository has no commits yet. gitctap publishes commits, it never makes them: "
            "git add . && git commit -m \"...\", then gitctap push"
        )
    branch = resolve_branch(root, args.branch)
    if rev_parse(root, "refs/heads/%s" % branch) is None:
        die("there is no local branch %r to publish" % branch)

    pending = dirty_files(root)
    out(
        "%s %s %s branch %s %s %d forge%s"
        % (
            TERM.bold("gitctap! push"),
            TERM.dot,
            config.get("name") or root.name,
            TERM.bold(branch),
            TERM.dot,
            len(forges),
            "" if len(forges) == 1 else "s",
        )
    )
    if pending:
        out(
            "%s %d uncommitted change%s stay on your disk: gitctap pushes commits only."
            % (TERM.alert, len(pending), "" if len(pending) == 1 else "s")
        )
    out()
    return do_pushes(
        root,
        forges,
        branch,
        tags=args.tags,
        dry_run=args.dry_run,
        quiet=args.quiet,
        set_upstream=args.set_upstream,
    )


def do_pushes(
    root: Path,
    forges: Sequence[dict],
    branch: str,
    tags: bool,
    dry_run: bool,
    quiet: bool,
    set_upstream: bool,
) -> int:
    results: List[Tuple[str, bool, str]] = []
    upstream_done = rev_parse(root, "refs/heads/%s@{upstream}" % branch) is not None

    for forge in forges:
        target = push_target(root, forge)
        out("%s %s %s %s" % (TERM.arrow, TERM.bold(forge["name"]), TERM.dot, forge["url"]))

        args: List[str] = ["push"]
        if dry_run:
            args.append("--dry-run")
        if set_upstream and not upstream_done and target == (forge.get("remote") or forge["name"]):
            args.append("--set-upstream")
        args += [target, "refs/heads/%s:refs/heads/%s" % (branch, branch)]

        code, stdout, stderr = (0, "", "")
        if quiet:
            code, stdout, stderr = run_git(args, cwd=root, network=True)
        else:
            code = stream_git(args, cwd=root)

        if code == 0 and tags:
            tag_args = ["push"]
            if dry_run:
                tag_args.append("--dry-run")
            tag_args += [target, "--tags"]
            if quiet:
                tag_code, _, tag_err = run_git(tag_args, cwd=root, network=True)
            else:
                tag_code, tag_err = stream_git(tag_args, cwd=root), ""
            if tag_code != 0:
                code, stderr = tag_code, tag_err or "pushing tags failed"

        if code == 0:
            if "--set-upstream" in args:
                upstream_done = True
            results.append((forge["name"], True, ""))
            out("  %s pushed" % TERM.ok)
        else:
            reason = explain("\n".join(filter(None, [stderr, stdout])) or "git push exited with code %d" % code)
            results.append((forge["name"], False, reason))
            out("  %s %s" % (TERM.bad, reason))
        out()

    width = column_width(forges)
    out(TERM.bold("result"))
    for name, good, reason in results:
        if good:
            out("  %-*s %s" % (width, name, TERM.ok))
        else:
            out("  %-*s %s %s" % (width, name, TERM.bad, reason))

    failed = [name for name, good, _ in results if not good]
    if failed:
        out()
        out(
            "%s %d of %d forges did not accept the push: %s"
            % (TERM.alert, len(failed), len(results), ", ".join(failed))
        )
        note("The forges that succeeded keep their commits. Nothing was rolled back, nothing was forced.")
        return 1
    if dry_run:
        out()
        note("this was a dry run: nothing was actually sent.")
    return 0


def forge_state(root: Path, forge: dict, branch: str, timeout: int, offline: bool) -> Tuple[str, str]:
    """Return (kind, text) where kind is one of ok, warn, fail."""
    local = rev_parse(root, "refs/heads/%s" % branch)
    if local is None:
        return "fail", "no local branch %s" % branch

    if offline:
        remote_ref = "refs/remotes/%s/%s" % (forge.get("remote") or forge["name"], branch)
        remote = rev_parse(root, remote_ref)
        if remote is None:
            return "warn", "never fetched locally (run gitctap status without --offline)"
        return compare_state(root, local, remote, "last known")

    code, stdout, stderr = ls_remote(forge["url"], branch, root, timeout)
    if code != 0:
        return "fail", explain(stderr or stdout)
    line = stdout.strip()
    if not line:
        return "warn", "branch %s is not published there yet" % branch
    remote = line.split()[0]
    return compare_state(root, local, remote, None)


def compare_state(root: Path, local: str, remote: str, prefix: Optional[str]) -> Tuple[str, str]:
    label = (prefix + ": ") if prefix else ""
    if local == remote:
        return "ok", label + "up to date"
    if not commit_exists(root, remote):
        return "warn", label + "out of sync, and its commits are unknown here (git fetch to compare)"
    code, stdout, _ = run_git(["rev-list", "--left-right", "--count", "%s...%s" % (remote, local)], cwd=root)
    if code != 0 or not stdout:
        return "warn", label + "out of sync"
    parts = stdout.split()
    try:
        remote_only = int(parts[0])
        local_only = int(parts[1])
    except (IndexError, ValueError):
        return "warn", label + "out of sync"
    if remote_only and local_only:
        return "warn", label + "diverged: %d commit%s behind, %d ahead" % (
            local_only,
            "" if local_only == 1 else "s",
            remote_only,
        )
    if local_only:
        return "warn", label + "%d commit%s behind" % (local_only, "" if local_only == 1 else "s")
    return "warn", label + "%d commit%s ahead of you (pull before you push)" % (
        remote_only,
        "" if remote_only == 1 else "s",
    )


def cmd_status(args: argparse.Namespace) -> int:
    root = require_repo(args)
    config = require_config(root)
    forges = list(config.get("forges", []))
    branch = resolve_branch(root, args.branch)

    out(
        "%s %s %s branch %s"
        % (TERM.bold(config.get("name") or root.name), TERM.dot, root, TERM.bold(branch))
    )
    pending = dirty_files(root)
    if pending:
        out("%s %d uncommitted change%s here, not part of any push" % (TERM.alert, len(pending), "" if len(pending) == 1 else "s"))
    if not has_commits(root):
        out("%s no commits yet" % TERM.alert)
    out()

    if args.fetch and not args.offline:
        for forge in forges:
            remote = forge.get("remote") or forge["name"]
            if list_remotes(root).get(remote) == forge["url"]:
                run_git(["fetch", "--quiet", remote], cwd=root, timeout=args.timeout, network=True)

    width = column_width(forges)
    problems = 0
    for forge in forges:
        kind, text = forge_state(root, forge, branch, args.timeout, args.offline)
        symbol = {"ok": TERM.ok, "warn": TERM.alert, "fail": TERM.bad}[kind]
        if kind != "ok":
            problems += 1
        out("%-*s %s %s" % (width, forge["name"], symbol, text))
    return 1 if problems else 0


def check_reachability(root: Path, forges: Sequence[dict], branch: Optional[str], timeout: int) -> List[str]:
    failures: List[str] = []
    width = column_width(forges)
    for forge in forges:
        code, stdout, stderr = ls_remote(forge["url"], None, root, timeout)
        if code != 0:
            failures.append(forge["name"])
            out("%-*s %s %s" % (width, forge["name"], TERM.bad, explain(stderr or stdout)))
            continue
        heads = [line for line in stdout.splitlines() if line.strip()]
        if not heads:
            out("%-*s %s reachable, still empty (your first push will fill it)" % (width, forge["name"], TERM.ok))
        elif branch and not any(line.endswith("refs/heads/%s" % branch) for line in heads):
            out(
                "%-*s %s reachable, %d branch%s, but not %s yet"
                % (width, forge["name"], TERM.ok, len(heads), "" if len(heads) == 1 else "es", branch)
            )
        else:
            out(
                "%-*s %s reachable, %d branch%s"
                % (width, forge["name"], TERM.ok, len(heads), "" if len(heads) == 1 else "es")
            )
    return failures


def cmd_check(args: argparse.Namespace) -> int:
    start = Path(args.chdir).expanduser() if args.chdir else Path.cwd()
    problems = 0

    out(TERM.bold("git"))
    binary = shutil.which("git")
    if not binary:
        out("  %s git is not installed or not in PATH" % TERM.bad)
        return 1
    _, version, _ = run_git(["--version"])
    out("  %s %s (%s)" % (TERM.ok, version or "git", binary))

    out()
    out(TERM.bold("repository"))
    root = find_repo_root(start) if start.is_dir() else None
    if root is None:
        out("  %s %s is not inside a Git repository" % (TERM.bad, start))
        note("run: git init, then gitctap setup")
        return 1
    out("  %s %s" % (TERM.ok, root))
    branch = args.branch or current_branch(root)
    if branch:
        out("  %s branch %s" % (TERM.ok, branch))
    else:
        problems += 1
        out("  %s HEAD is detached, no branch to publish" % TERM.alert)
    if has_commits(root):
        _, count, _ = run_git(["rev-list", "--count", "HEAD"], cwd=root)
        out("  %s %s commit%s" % (TERM.ok, count or "?", "" if count == "1" else "s"))
    else:
        problems += 1
        out("  %s no commits yet" % TERM.alert)
    pending = dirty_files(root)
    if pending:
        out("  %s %d uncommitted change%s (gitctap never commits them for you)" % (TERM.alert, len(pending), "" if len(pending) == 1 else "s"))
    else:
        out("  %s working tree clean" % TERM.ok)

    out()
    out(TERM.bold("configuration"))
    config = load_config(root)
    if config is None:
        out("  %s no gitctap configuration for this project" % TERM.bad)
        note("run: gitctap setup")
        return 1
    out("  %s %s" % (TERM.ok, config.get("_path")))
    forges = list(config.get("forges", []))
    if not forges:
        out("  %s no forges configured" % TERM.bad)
        note("run: gitctap add <name> <url>")
        return 1
    out("  %s project %s, %d forge%s" % (TERM.ok, config.get("name") or root.name, len(forges), "" if len(forges) == 1 else "s"))

    out()
    out(TERM.bold("git remotes"))
    known = list_remotes(root)
    width = column_width(forges)
    for forge in forges:
        remote = forge.get("remote") or forge["name"]
        actual = known.get(remote)
        if actual is None:
            problems += 1
            out("  %-*s %s no remote %r yet, gitctap will push to the URL" % (width, forge["name"], TERM.alert, remote))
        elif actual != forge["url"]:
            problems += 1
            out("  %-*s %s remote %r points at %s" % (width, forge["name"], TERM.alert, remote, actual))
            note("config says %s; gitctap pushes to the config URL" % forge["url"])
        else:
            out("  %-*s %s %s" % (width, forge["name"], TERM.ok, actual))

    if args.offline:
        out()
        note("--offline: the forges themselves were not contacted.")
        return 1 if problems else 0

    out()
    out(TERM.bold("forges"))
    failures = check_reachability(root, forges, branch, args.timeout)
    problems += len(failures)

    out()
    if problems:
        out("%s %d thing%s to look at above." % (TERM.alert, problems, "" if problems == 1 else "s"))
        return 1
    out("%s everything is ready. gitctap push will work." % TERM.ok)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    root = require_repo(args)
    config = load_config(root)
    if config is None:
        die("no gitctap configuration for %s yet. Run: gitctap setup" % root)
        return 1

    try:
        name = check_forge_name(args.name)
    except ValueError as problem:
        die(str(problem))
        return 1
    for forge in config.get("forges", []):
        if forge["name"] == name:
            die("forge %r is already configured (%s). Use gitctap remove %s first." % (name, forge["url"], name))

    raw = args.url or ask("Clone URL for %s" % name)
    try:
        url = normalize_url(raw)
    except ValueError as problem:
        die(str(problem))
        return 1
    for forge in config.get("forges", []):
        if forge["url"] == url:
            die("that URL is already configured as %r" % forge["name"])
    if WEB_PATH_RE.search(url):
        out("%s %s looks like a page in the web interface, not a clone URL" % (TERM.alert, url))

    entry = {"name": name, "url": url, "remote": name}
    config.setdefault("forges", []).append(entry)

    good, stderr = set_remote(root, name, url)
    if good:
        out("%s git remote %s %s %s" % (TERM.ok, TERM.bold(name), TERM.dot, url))
    else:
        out("%s could not set the git remote: %s" % (TERM.alert, explain(stderr)))

    path = save_config(root, config)
    out("%s %s added to %s" % (TERM.ok, name, path))

    if not args.no_check:
        code, stdout, stderr = ls_remote(url, None, root, args.timeout)
        if code != 0:
            out("%s not reachable yet: %s" % (TERM.alert, explain(stderr or stdout)))
            return 1
        heads = [line for line in stdout.splitlines() if line.strip()]
        out("%s reachable, %d branch%s there" % (TERM.ok, len(heads), "" if len(heads) == 1 else "es"))
    note("nothing was pushed. Run: gitctap push")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    root = require_repo(args)
    config = require_config(root)
    name = (args.name or "").strip().lower()
    forges = config.get("forges", [])
    target = next((forge for forge in forges if forge["name"] == name), None)
    if target is None:
        die("no forge %r in this project. Configured: %s" % (name, ", ".join(forge["name"] for forge in forges) or "none"))
        return 1

    out("%s removes %s (%s) from the gitctap configuration only." % (TERM.bold("remove"), name, target["url"]))
    note("The repository on the forge, its branches and its commits are left exactly as they are.")
    if not args.yes and not ask_yes_no("Remove %s from this project?" % name, default=False):
        note("nothing was changed.")
        return 0

    config["forges"] = [forge for forge in forges if forge["name"] != name]
    path = save_config(root, config)
    out("%s %s removed from %s" % (TERM.ok, name, path))

    remote = target.get("remote") or name
    if list_remotes(root).get(remote) is not None and not args.keep_remote:
        drop = args.yes or ask_yes_no("Also delete the local git remote %r?" % remote, default=False)
        if drop:
            code, _, stderr = run_git(["remote", "remove", remote], cwd=root)
            if code == 0:
                out("%s local git remote %s deleted (local bookkeeping only)" % (TERM.ok, remote))
            else:
                out("%s could not delete the local remote: %s" % (TERM.alert, explain(stderr)))
        else:
            note("local git remote %r kept, so git push %s still works by hand." % (remote, remote))
    return 0


def print_forges(config: dict) -> None:
    forges = list(config.get("forges", []))
    if not forges:
        note("no forges configured")
        return
    width = column_width(forges)
    for forge in forges:
        out("  %-*s %s" % (width, forge["name"], forge["url"]))


def cmd_list(args: argparse.Namespace) -> int:
    root = require_repo(args)
    config = load_config(root)
    if config is None:
        die("no gitctap configuration for %s yet. Run: gitctap setup" % root)
        return 1
    forges = list(config.get("forges", []))
    out("%s %s %s" % (TERM.bold(config.get("name") or root.name), TERM.dot, root))
    out()
    if not forges:
        out("no forges yet. Add one: gitctap add <name> <url>")
        return 0
    known = list_remotes(root)
    width = column_width(forges)
    for forge in forges:
        remote = forge.get("remote") or forge["name"]
        host = url_host(forge["url"]) or "local path"
        mark = TERM.ok if known.get(remote) == forge["url"] else TERM.alert
        out("%-*s %s %-16s %s" % (width, TERM.bold(forge["name"]), mark, host, forge["url"]))
    out()
    note("%d forge%s %s config: %s" % (len(forges), "" if len(forges) == 1 else "s", TERM.dot, config.get("_path")))
    return 0


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


EPILOG = """\
usual work:
  git add .
  git commit -m "what changed"
  gitctap push

gitctap publishes commits that Git already made. It never commits for you,
never force-pushes, never mirrors, and never deletes anything on a forge.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitctap",
        description="gitctap! - one local Git project, several Git forges, one command.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-C", dest="chdir", metavar="PATH", help="work in this directory instead of the current one")
    parser.add_argument("--no-color", action="store_true", help="plain output, no ANSI colours")
    parser.add_argument("--ascii", action="store_true", help="ASCII marks instead of check marks")
    parser.add_argument("--version", action="version", version="gitctap! %s" % VERSION)
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    setup = subparsers.add_parser("setup", help="set the project up: forges, remotes, access")
    setup.add_argument("--name", help="project name (default: folder name)")
    setup.add_argument(
        "--forge",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="add a forge without questions, repeatable (also accepts a bare URL)",
    )
    setup.add_argument("--init", action="store_true", help="git init without asking if this is not a repository")
    setup.add_argument("--test-push", action="store_true", help="do the first push at the end (this is the explicit confirmation)")
    setup.add_argument("--no-push", action="store_true", help="never offer the first push")
    setup.add_argument("--no-check", action="store_true", help="skip contacting the forges")
    setup.add_argument("--force", action="store_true", help="replace an existing configuration without asking")
    setup.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SEC", help="network timeout per forge")
    setup.set_defaults(handler=cmd_setup)

    push = subparsers.add_parser("push", help="send the current branch to every configured forge")
    push.add_argument("--branch", help="branch to publish (default: the one you are on)")
    push.add_argument("--tags", action="store_true", help="also push tags")
    push.add_argument("--only", action="append", default=[], metavar="FORGE", help="only this forge, repeatable")
    push.add_argument("--skip", action="append", default=[], metavar="FORGE", help="skip this forge, repeatable")
    push.add_argument("--dry-run", action="store_true", help="ask Git what it would send, send nothing")
    push.add_argument("--quiet", action="store_true", help="hide Git's own output (non-interactive: no credential prompts)")
    push.add_argument("--set-upstream", action="store_true", help="set the upstream branch on the first forge if there is none")
    push.set_defaults(handler=cmd_push)

    status = subparsers.add_parser("status", help="show how far each forge is from your branch")
    status.add_argument("--branch", help="branch to compare (default: the one you are on)")
    status.add_argument("--offline", action="store_true", help="use what Git already knows, contact nobody")
    status.add_argument("--fetch", action="store_true", help="fetch first, for exact counts")
    status.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SEC", help="network timeout per forge")
    status.set_defaults(handler=cmd_status)

    check = subparsers.add_parser("check", help="check git, config, access and branches, publish nothing")
    check.add_argument("--branch", help="branch to look for on the forges")
    check.add_argument("--offline", action="store_true", help="local checks only")
    check.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SEC", help="network timeout per forge")
    check.set_defaults(handler=cmd_check)

    add = subparsers.add_parser("add", help="add one more forge to this project")
    add.add_argument("name", help="short name, also used as the git remote name")
    add.add_argument("url", nargs="?", help="clone URL (asked for if omitted)")
    add.add_argument("--no-check", action="store_true", help="do not contact the forge")
    add.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SEC", help="network timeout")
    add.set_defaults(handler=cmd_add)

    remove = subparsers.add_parser("remove", help="drop a forge from the configuration (never from the forge)")
    remove.add_argument("name", help="forge to forget")
    remove.add_argument("--keep-remote", action="store_true", help="leave the local git remote alone")
    remove.add_argument("-y", "--yes", action="store_true", help="do not ask")
    remove.set_defaults(handler=cmd_remove)

    listing = subparsers.add_parser("list", help="show every configured forge")
    listing.set_defaults(handler=cmd_list)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    global TERM
    TERM = Term(detect_color(args.no_color), detect_unicode(args.ascii))

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        out()
        out("start with: gitctap setup")
        return 0
    try:
        return int(handler(args) or 0)
    except KeyboardInterrupt:
        out()
        eout("%s aborted, nothing was changed" % TERM.bad)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
