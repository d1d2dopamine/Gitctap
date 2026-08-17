#!/usr/bin/env python3
"""Tests for gitctap!.

The "forges" here are bare repositories in a temporary folder, so the whole
suite runs offline and touches nothing outside the temporary directory.

    python3 -m unittest discover -s tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITCTAP = ROOT / "gitctap.py"


def git(args, cwd):
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "gitctap tests"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "tests@example.invalid"
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
    ).stdout


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class GitctapTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gitctap-test-"))
        self.config_dir = self.tmp / "config"
        self.project = self.tmp / "project"
        self.project.mkdir()
        git(["init", "--quiet"], self.project)
        git(["config", "user.name", "gitctap tests"], self.project)
        git(["config", "user.email", "tests@example.invalid"], self.project)
        git(["symbolic-ref", "HEAD", "refs/heads/main"], self.project)
        (self.project / "README.md").write_text("hello\n", encoding="utf-8")
        git(["add", "."], self.project)
        git(["commit", "--quiet", "-m", "first"], self.project)

        self.forges = {}
        for name in ("github", "codeberg"):
            path = self.tmp / ("%s.git" % name)
            git(["init", "--bare", "--quiet", str(path)], self.tmp)
            self.forges[name] = path

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_gitctap(self, *args, cwd=None, expect=0):
        env = os.environ.copy()
        env["GITCTAP_CONFIG_DIR"] = str(self.config_dir)
        env["NO_COLOR"] = "1"
        env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "gitctap tests"
        env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "tests@example.invalid"
        done = subprocess.run(
            [sys.executable, str(GITCTAP), *args],
            cwd=str(cwd or self.project),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if expect is not None:
            self.assertEqual(
                done.returncode,
                expect,
                "expected exit %s, got %s\n%s" % (expect, done.returncode, done.stdout),
            )
        return done.stdout

    def setup_project(self, *forges):
        names = forges or ("github", "codeberg")
        args = ["setup", "--name", "demo", "--no-push"]
        for name in names:
            args += ["--forge", "%s=%s" % (name, self.forges[name])]
        return self.run_gitctap(*args)

    def config_json(self):
        files = sorted((self.config_dir / "projects").glob("*.json"))
        self.assertEqual(len(files), 1, "expected exactly one configuration file")
        return json.loads(files[0].read_text(encoding="utf-8"))

    def remote_head(self, name, branch="main"):
        out = git(["ls-remote", str(self.forges[name]), "refs/heads/%s" % branch], self.project)
        return out.split()[0] if out.strip() else None

    # --- setup ------------------------------------------------------------ #

    def test_setup_writes_config_outside_the_repository(self):
        self.setup_project()
        data = self.config_json()
        self.assertEqual(data["gitctap"], 1)
        self.assertEqual(data["name"], "demo")
        self.assertEqual([forge["name"] for forge in data["forges"]], ["github", "codeberg"])
        self.assertFalse((self.project / ".gitctap.toml").exists())
        self.assertFalse((self.project / ".gitctap.json").exists())
        # nothing new inside the repository
        self.assertEqual(git(["status", "--porcelain"], self.project).strip(), "")

    def test_setup_creates_git_remotes(self):
        self.setup_project()
        remotes = git(["remote"], self.project).split()
        self.assertIn("github", remotes)
        self.assertIn("codeberg", remotes)

    def test_setup_does_not_push_on_its_own(self):
        self.setup_project()
        self.assertIsNone(self.remote_head("github"))
        self.assertIsNone(self.remote_head("codeberg"))

    def test_setup_can_init_a_repository(self):
        fresh = self.tmp / "fresh"
        fresh.mkdir()
        self.run_gitctap(
            "setup",
            "--init",
            "--no-push",
            "--forge",
            "github=%s" % self.forges["github"],
            cwd=fresh,
        )
        self.assertTrue((fresh / ".git").is_dir())

    def test_setup_refuses_duplicate_urls(self):
        out = self.run_gitctap(
            "setup",
            "--no-push",
            "--forge",
            "github=%s" % self.forges["github"],
            "--forge",
            "mirror=%s" % self.forges["github"],
            expect=1,
        )
        self.assertIn("twice", out)

    def test_setup_test_push_flag_publishes(self):
        self.run_gitctap(
            "setup",
            "--test-push",
            "--forge",
            "github=%s" % self.forges["github"],
        )
        self.assertIsNotNone(self.remote_head("github"))

    # --- push ------------------------------------------------------------- #

    def test_push_publishes_to_every_forge(self):
        self.setup_project()
        out = self.run_gitctap("push")
        local = git(["rev-parse", "HEAD"], self.project).strip()
        self.assertEqual(self.remote_head("github"), local)
        self.assertEqual(self.remote_head("codeberg"), local)
        self.assertIn("github", out)
        self.assertIn("codeberg", out)

    def test_push_reports_each_forge_separately(self):
        self.setup_project()
        broken = self.tmp / "gone.git"
        self.run_gitctap("add", "gitlab", str(broken), "--no-check")
        out = self.run_gitctap("push", expect=1)
        self.assertIn("github", out)
        # the working forges still got the commits
        self.assertIsNotNone(self.remote_head("github"))
        self.assertIsNotNone(self.remote_head("codeberg"))

    def test_push_never_forces(self):
        self.setup_project("github")
        self.run_gitctap("push")
        # the forge moves ahead on its own
        clone = self.tmp / "clone"
        git(["clone", "--quiet", "--branch", "main", str(self.forges["github"]), str(clone)], self.tmp)
        git(["config", "user.name", "other"], clone)
        git(["config", "user.email", "other@example.invalid"], clone)
        (clone / "other.txt").write_text("theirs\n", encoding="utf-8")
        git(["add", "."], clone)
        git(["commit", "--quiet", "-m", "theirs"], clone)
        git(["push", "--quiet", "origin", "main"], clone)
        forge_head = self.remote_head("github")

        # our own divergent commit
        (self.project / "mine.txt").write_text("mine\n", encoding="utf-8")
        git(["add", "."], self.project)
        git(["commit", "--quiet", "-m", "mine"], self.project)

        out = self.run_gitctap("push", "--quiet", expect=1)
        self.assertIn("never force", out)
        # the forge still holds the other commit: nothing was overwritten
        self.assertEqual(self.remote_head("github"), forge_head)

    def test_push_only_and_skip(self):
        self.setup_project()
        self.run_gitctap("push", "--only", "github")
        self.assertIsNotNone(self.remote_head("github"))
        self.assertIsNone(self.remote_head("codeberg"))
        self.run_gitctap("push", "--skip", "github")
        self.assertIsNotNone(self.remote_head("codeberg"))

    def test_push_dry_run_sends_nothing(self):
        self.setup_project()
        self.run_gitctap("push", "--dry-run")
        self.assertIsNone(self.remote_head("github"))

    def test_push_tags_only_with_the_flag(self):
        self.setup_project("github")
        git(["tag", "v0.1.0"], self.project)
        self.run_gitctap("push")
        tags = git(["ls-remote", "--tags", str(self.forges["github"])], self.project)
        self.assertNotIn("v0.1.0", tags)
        self.run_gitctap("push", "--tags")
        tags = git(["ls-remote", "--tags", str(self.forges["github"])], self.project)
        self.assertIn("v0.1.0", tags)

    def test_push_without_config_explains_itself(self):
        out = self.run_gitctap("push", expect=1)
        self.assertIn("gitctap setup", out)

    def test_push_without_commits_refuses(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        git(["init", "--quiet"], empty)
        self.run_gitctap(
            "setup", "--no-push", "--no-check", "--forge", "github=%s" % self.forges["github"], cwd=empty
        )
        out = self.run_gitctap("push", cwd=empty, expect=1)
        self.assertIn("no commits", out)

    def test_push_warns_about_uncommitted_changes(self):
        self.setup_project("github")
        (self.project / "draft.txt").write_text("wip\n", encoding="utf-8")
        out = self.run_gitctap("push")
        self.assertIn("uncommitted", out)

    # --- status / check / list / add / remove ----------------------------- #

    def test_status_reports_up_to_date_and_behind(self):
        self.setup_project()
        self.run_gitctap("push", "--only", "github")
        out = self.run_gitctap("status", expect=1)
        self.assertIn("up to date", out)
        self.assertIn("not published", out)

        self.run_gitctap("push", "--only", "codeberg")
        out = self.run_gitctap("status")
        self.assertEqual(out.count("up to date"), 2)

        (self.project / "more.txt").write_text("more\n", encoding="utf-8")
        git(["add", "."], self.project)
        git(["commit", "--quiet", "-m", "second"], self.project)
        out = self.run_gitctap("status", expect=1)
        self.assertIn("1 commit behind", out)

    def test_check_passes_on_a_ready_project(self):
        self.setup_project()
        out = self.run_gitctap("check")
        self.assertIn("gitctap push will work", out)

    def test_check_without_config_fails(self):
        out = self.run_gitctap("check", expect=1)
        self.assertIn("gitctap setup", out)

    def test_list_shows_forges(self):
        self.setup_project()
        out = self.run_gitctap("list")
        self.assertIn("github", out)
        self.assertIn("codeberg", out)

    def test_add_and_remove(self):
        self.setup_project("github")
        third = self.tmp / "gitlab.git"
        git(["init", "--bare", "--quiet", str(third)], self.tmp)
        self.run_gitctap("add", "gitlab", str(third))
        self.assertIn("gitlab", [forge["name"] for forge in self.config_json()["forges"]])

        self.run_gitctap("remove", "gitlab", "--yes", "--keep-remote")
        self.assertNotIn("gitlab", [forge["name"] for forge in self.config_json()["forges"]])
        # the "forge" itself is untouched
        self.assertTrue(third.is_dir())
        # and the local remote was kept because we asked for that
        self.assertIn("gitlab", git(["remote"], self.project).split())

    def test_remove_never_deletes_the_remote_repository(self):
        self.setup_project("github")
        self.run_gitctap("push")
        head = self.remote_head("github")
        self.run_gitctap("remove", "github", "--yes")
        self.assertTrue(self.forges["github"].is_dir())
        self.assertEqual(
            git(["ls-remote", str(self.forges["github"]), "refs/heads/main"], self.project).split()[0],
            head,
        )

    def test_add_rejects_a_duplicate_url(self):
        self.setup_project("github")
        out = self.run_gitctap("add", "mirror", str(self.forges["github"]), expect=1)
        self.assertIn("already configured", out)

    def test_add_rejects_a_bad_name(self):
        self.setup_project("github")
        out = self.run_gitctap("add", "Bad Name", str(self.forges["codeberg"]), expect=1)
        self.assertIn("not usable", out)

    def test_config_survives_a_renamed_folder(self):
        self.setup_project("github")
        moved = self.tmp / "project-renamed"
        self.project.rename(moved)
        out = self.run_gitctap("list", cwd=moved, expect=1)
        self.assertIn("gitctap setup", out)

    def test_version_and_help(self):
        self.assertIn("gitctap!", self.run_gitctap("--version"))
        self.assertIn("gitctap push", self.run_gitctap("--help"))


class PureHelperTestCase(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT))
        import gitctap

        self.gitctap = gitctap

    def test_forge_name_guessing(self):
        cases = {
            "git@github.com:user/repo.git": "github",
            "https://codeberg.org/user/repo.git": "codeberg",
            "https://gitlab.com/user/repo": "gitlab",
            "ssh://git@git.sr.ht/~user/repo": "sourcehut",
            "https://git.example.org/user/repo.git": "example",
        }
        for url, expected in cases.items():
            self.assertEqual(self.gitctap.guess_forge_name(url), expected, url)

    def test_url_host(self):
        self.assertEqual(self.gitctap.url_host("git@github.com:u/r.git"), "github.com")
        self.assertEqual(self.gitctap.url_host("https://user@gitlab.com/u/r"), "gitlab.com")
        self.assertIsNone(self.gitctap.url_host("/srv/git/repo.git"))

    def test_normalize_url(self):
        self.assertEqual(self.gitctap.normalize_url("  https://x.org/a/b/  "), "https://x.org/a/b")
        with self.assertRaises(ValueError):
            self.gitctap.normalize_url("   ")
        with self.assertRaises(ValueError):
            self.gitctap.normalize_url("https://x.org/a b")

    def test_error_hints_are_human(self):
        self.assertIn("never force", self.gitctap.explain("! [rejected] main -> main (non-fast-forward)"))
        self.assertIn("SSH key", self.gitctap.explain("git@github.com: Permission denied (publickey)."))
        self.assertIn("repository not found", self.gitctap.explain("remote: Repository not found."))

    def test_forge_name_validation(self):
        self.assertEqual(self.gitctap.check_forge_name(" GitHub "), "github")
        with self.assertRaises(ValueError):
            self.gitctap.check_forge_name("has space")


if __name__ == "__main__":
    unittest.main()
