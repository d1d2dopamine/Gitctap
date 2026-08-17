#!/usr/bin/env python3
"""Tests for `gitctap create`, the only part of gitctap that talks to a forge API.

Nothing here touches the network. The request builders and the response readers
are pure functions, so they are called directly, and the command itself is only
exercised with --dry-run, which creates nothing and saves nothing.

Run with:
    python3 -m unittest discover -s tests
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "gitctap.py"

_spec = importlib.util.spec_from_file_location("gitctap_module", SCRIPT)
gitctap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gitctap)


class ResolveTargetTests(unittest.TestCase):
    def test_known_forges(self):
        github = gitctap.resolve_create_target("github")
        self.assertEqual(github["kind"], "github")
        self.assertEqual(github["host"], "github.com")
        self.assertEqual(github["api"], "https://api.github.com")

        codeberg = gitctap.resolve_create_target("codeberg")
        self.assertEqual(codeberg["kind"], "gitea")
        self.assertEqual(codeberg["api"], "https://codeberg.org/api/v1")

        gitlab = gitctap.resolve_create_target("gitlab")
        self.assertEqual(gitlab["kind"], "gitlab")
        self.assertEqual(gitlab["api"], "https://gitlab.com/api/v4")

    def test_a_known_forge_under_another_short_name(self):
        target = gitctap.resolve_create_target("mirror=codeberg")
        self.assertEqual(target["name"], "mirror")
        self.assertEqual(target["kind"], "gitea")
        self.assertEqual(target["host"], "codeberg.org")

    def test_self_hosted_forge_with_its_kind_spelled_out(self):
        target = gitctap.resolve_create_target("work=gitea:git.example.org")
        self.assertEqual(target["name"], "work")
        self.assertEqual(target["kind"], "gitea")
        self.assertEqual(target["host"], "git.example.org")
        self.assertEqual(target["api"], "https://git.example.org/api/v1")

    def test_a_bare_unknown_host_is_refused_with_the_fix_in_the_message(self):
        with self.assertRaises(ValueError) as caught:
            gitctap.resolve_create_target("git.example.org")
        message = str(caught.exception)
        self.assertIn("gitea", message)
        self.assertIn("--on", message)

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            gitctap.resolve_create_target("work=svn:git.example.org")

    def test_empty_value_is_refused(self):
        with self.assertRaises(ValueError):
            gitctap.resolve_create_target("")

    def test_github_enterprise_api_path(self):
        self.assertEqual(
            gitctap.api_base_for_host("github", "git.company.com"),
            "https://git.company.com/api/v3",
        )


class RequestBuildingTests(unittest.TestCase):
    def test_github_personal_repository(self):
        request = gitctap.build_create_request("github", "https://api.github.com", "demo", "tok")
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], "https://api.github.com/user/repos")
        self.assertEqual(request["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(request["payload"]["name"], "demo")
        self.assertTrue(request["payload"]["private"])
        self.assertFalse(request["payload"]["auto_init"])

    def test_github_organisation_repository(self):
        request = gitctap.build_create_request(
            "github", "https://api.github.com", "demo", "tok", owner="my-org", private=False
        )
        self.assertEqual(request["url"], "https://api.github.com/orgs/my-org/repos")
        self.assertFalse(request["payload"]["private"])

    def test_gitea_repository(self):
        request = gitctap.build_create_request(
            "gitea", "https://codeberg.org/api/v1", "demo", "tok", description="hello"
        )
        self.assertEqual(request["url"], "https://codeberg.org/api/v1/user/repos")
        self.assertEqual(request["headers"]["Authorization"], "token tok")
        self.assertEqual(request["payload"]["description"], "hello")
        self.assertFalse(request["payload"]["auto_init"])

    def test_gitlab_repository(self):
        request = gitctap.build_create_request(
            "gitlab", "https://gitlab.com/api/v4", "demo", "tok", namespace_id=42
        )
        self.assertEqual(request["url"], "https://gitlab.com/api/v4/projects")
        self.assertEqual(request["headers"]["PRIVATE-TOKEN"], "tok")
        self.assertEqual(request["payload"]["visibility"], "private")
        self.assertEqual(request["payload"]["namespace_id"], 42)
        self.assertFalse(request["payload"]["initialize_with_readme"])

    def test_identity_and_namespace_requests_are_read_only(self):
        identity = gitctap.build_identity_request("github", "https://api.github.com", "tok")
        self.assertEqual(identity["method"], "GET")
        self.assertEqual(identity["url"], "https://api.github.com/user")
        self.assertIsNone(identity["payload"])

        namespace = gitctap.build_namespace_request("https://gitlab.com/api/v4", "my-group", "tok")
        self.assertEqual(namespace["method"], "GET")
        self.assertIn("search=my-group", namespace["url"])

    def test_an_unknown_kind_cannot_build_a_request(self):
        with self.assertRaises(ValueError):
            gitctap.build_create_request("svn", "https://example.org", "demo", "tok")


class SafetyTests(unittest.TestCase):
    def test_only_get_and_post_are_ever_sent(self):
        with self.assertRaises(ValueError):
            gitctap.api_call({"method": "DELETE", "url": "https://example.invalid", "headers": {}}, 1)
        with self.assertRaises(ValueError):
            gitctap.api_call({"method": "PATCH", "url": "https://example.invalid", "headers": {}}, 1)

    def test_source_contains_no_destructive_http_verb(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for verb in ("DELETE", "PATCH", "PUT"):
            self.assertNotIn('"%s"' % verb, source)

    def test_source_never_force_pushes_or_mirrors(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for flag in ('"--mirror"', '"--force-with-lease"', '"+refs/heads/', '"--delete"'):
            self.assertNotIn(flag, source)
        # "--force" exists exactly once, and only as `setup --force`, which replaces a
        # local configuration and never touches a forge.
        self.assertEqual(source.count('"--force"'), 1)
        self.assertIn('setup.add_argument("--force"', source)

    def test_new_repositories_are_never_pre_filled(self):
        for kind, api in (("github", "https://api.github.com"), ("gitea", "https://codeberg.org/api/v1")):
            payload = gitctap.build_create_request(kind, api, "demo", "tok")["payload"]
            self.assertFalse(payload["auto_init"])


class ResponseReadingTests(unittest.TestCase):
    def test_github_payload_urls(self):
        urls = gitctap.clone_urls_from_payload(
            "github",
            {
                "ssh_url": "git@github.com:me/demo.git",
                "clone_url": "https://github.com/me/demo.git",
                "html_url": "https://github.com/me/demo",
                "owner": {"login": "me"},
            },
        )
        self.assertEqual(urls["ssh"], "git@github.com:me/demo.git")
        self.assertEqual(urls["owner"], "me")

    def test_gitlab_payload_urls(self):
        urls = gitctap.clone_urls_from_payload(
            "gitlab",
            {
                "ssh_url_to_repo": "git@gitlab.com:me/demo.git",
                "http_url_to_repo": "https://gitlab.com/me/demo.git",
                "web_url": "https://gitlab.com/me/demo",
                "namespace": {"full_path": "me"},
            },
        )
        self.assertEqual(urls["https"], "https://gitlab.com/me/demo.git")
        self.assertEqual(urls["owner"], "me")

    def test_urls_can_be_constructed_when_the_forge_is_terse(self):
        urls = gitctap.construct_clone_urls("codeberg.org", "me", "demo")
        self.assertEqual(urls["ssh"], "git@codeberg.org:me/demo.git")
        self.assertEqual(urls["https"], "https://codeberg.org/me/demo.git")
        self.assertEqual(urls["web"], "https://codeberg.org/me/demo")

    def test_login_and_namespace_reading(self):
        self.assertEqual(gitctap.login_from_payload("github", {"login": "me"}), "me")
        self.assertEqual(gitctap.login_from_payload("gitea", {"username": "me"}), "me")
        self.assertIsNone(gitctap.login_from_payload("github", None))
        self.assertEqual(
            gitctap.namespace_id_from_payload([{"full_path": "my-group", "id": 7}], "my-group"), 7
        )
        self.assertIsNone(gitctap.namespace_id_from_payload([{"full_path": "other", "id": 7}], "my-group"))

    def test_an_existing_repository_is_recognised(self):
        self.assertTrue(gitctap.looks_existing("name already exists on this account", None))
        self.assertTrue(gitctap.looks_existing("", {"message": ["has already been taken"]}))
        self.assertFalse(gitctap.looks_existing("some other problem", None))

    def test_failures_are_explained_in_one_line(self):
        self.assertIn("token rejected", gitctap.api_reason(401, None, "", "github"))
        self.assertIn("token rejected", gitctap.api_reason(403, None, "", "github"))
        self.assertIn("404", gitctap.api_reason(404, None, "", "gitea"))
        self.assertIn("rate limited", gitctap.api_reason(429, None, "", "gitlab"))
        self.assertIn("could not be reached", gitctap.api_reason(0, None, "", "github"))
        self.assertIn("bad name", gitctap.api_reason(422, {"message": "bad name"}, "", "github"))

    def test_cli_command_lines(self):
        self.assertEqual(
            gitctap.build_cli_create_argv("github", "demo"),
            ["gh", "repo", "create", "demo", "--private"],
        )
        self.assertEqual(
            gitctap.build_cli_create_argv("github", "demo", owner="my-org", private=False),
            ["gh", "repo", "create", "my-org/demo", "--public"],
        )
        self.assertEqual(
            gitctap.build_cli_create_argv("gitea", "demo"),
            ["tea", "repos", "create", "--name", "demo", "--private"],
        )
        self.assertEqual(
            gitctap.build_cli_create_argv("gitlab", "demo", owner="my-group"),
            ["glab", "repo", "create", "demo", "--private", "--group", "my-group"],
        )

    def test_owner_is_found_in_cli_chatter(self):
        self.assertEqual(
            gitctap.extract_repo_owner("Created repository me/demo on GitHub", "github.com", "demo"),
            "me",
        )
        self.assertEqual(
            gitctap.extract_repo_owner("https://codeberg.org/me/demo.git", "codeberg.org", "demo"),
            "me",
        )
        self.assertIsNone(gitctap.extract_repo_owner("nothing useful here", "github.com", "demo"))

    def test_token_environment_variables(self):
        names = gitctap.token_env_names("github", "github")
        self.assertEqual(names[0], "GITCTAP_GITHUB_TOKEN")
        self.assertIn("GITHUB_TOKEN", names)
        self.assertIn("CODEBERG_TOKEN", gitctap.token_env_names("codeberg", "gitea"))
        self.assertEqual(gitctap.token_env_names("my-forge", "gitea")[0], "GITCTAP_MY_FORGE_TOKEN")

    def test_a_renamed_forge_still_uses_its_own_token(self):
        names = gitctap.token_env_names("mirror", "gitea", "codeberg")
        self.assertEqual(names[0], "GITCTAP_MIRROR_TOKEN")
        self.assertIn("CODEBERG_TOKEN", names)
        self.assertIn("GITEA_TOKEN", names)
        self.assertEqual(gitctap.resolve_create_target("mirror=codeberg")["alias"], "codeberg")
        self.assertIsNone(gitctap.resolve_create_target("work=gitea:git.example.org")["alias"])

    def test_an_installed_cli_can_be_switched_off(self):
        previous = os.environ.get("GITCTAP_DISABLE_CLI")
        os.environ["GITCTAP_DISABLE_CLI"] = "1"
        try:
            self.assertIsNone(gitctap.cli_tool_for("github"))
        finally:
            if previous is None:
                os.environ.pop("GITCTAP_DISABLE_CLI", None)
            else:
                os.environ["GITCTAP_DISABLE_CLI"] = previous


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class CreateCommandTests(unittest.TestCase):
    """The command itself, always with --dry-run so no forge is ever contacted."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gitctap-create-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.config_dir = self.tmp / "config"
        self.project = self.tmp / "proj"
        self.project.mkdir()

    def run_gitctap(self, *args, **kwargs):
        expect = kwargs.pop("expect", 0)
        extra = kwargs.pop("env", {})
        env = {key: value for key, value in os.environ.items() if not key.endswith("_TOKEN")}
        env.update(
            {
                "GITCTAP_CONFIG_DIR": str(self.config_dir),
                "GITCTAP_DISABLE_CLI": "1",
                "NO_COLOR": "1",
            }
        )
        env.update(extra)
        done = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(self.project),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = done.stdout.decode("utf-8", "replace")
        self.assertEqual(done.returncode, expect, "expected exit %d, got %d:\n%s" % (expect, done.returncode, output))
        return output

    def test_without_a_forge_it_refuses(self):
        output = self.run_gitctap("create", "demo", expect=1)
        self.assertIn("--on", output)

    def test_without_credentials_it_says_so_and_creates_nothing(self):
        output = self.run_gitctap("create", "demo", "--on", "github", "--dry-run", expect=1)
        self.assertIn("no credentials", output)
        self.assertIn("GITHUB_TOKEN", output)
        self.assertFalse(self.config_dir.exists())

    def test_the_plan_names_the_token_it_would_use(self):
        output = self.run_gitctap(
            "create",
            "demo",
            "--on",
            "github",
            "--on",
            "mirror=codeberg",
            "--dry-run",
            env={"GITHUB_TOKEN": "fake", "CODEBERG_TOKEN": "fake"},
        )
        self.assertIn("$GITHUB_TOKEN", output)
        self.assertIn("$CODEBERG_TOKEN", output)
        self.assertIn("github.com", output)
        self.assertIn("codeberg.org", output)
        self.assertIn("nothing was created", output)
        self.assertFalse(self.config_dir.exists())

    def test_private_by_default_and_public_on_request(self):
        private = self.run_gitctap(
            "create", "demo", "--on", "github", "--dry-run", env={"GITHUB_TOKEN": "fake"}
        )
        self.assertIn("private", private)
        public = self.run_gitctap(
            "create", "demo", "--on", "github", "--public", "--dry-run", env={"GITHUB_TOKEN": "fake"}
        )
        self.assertIn("public", public)

    def test_an_unknown_host_is_refused_before_anything_happens(self):
        output = self.run_gitctap("create", "demo", "--on", "git.example.org", "--dry-run", expect=1)
        self.assertIn("gitea", output)
        self.assertFalse(self.config_dir.exists())

    def test_an_unusable_repository_name_is_refused(self):
        output = self.run_gitctap(
            "create", "not a name", "--on", "github", "--dry-run", expect=1, env={"GITHUB_TOKEN": "fake"}
        )
        self.assertIn("not a usable repository name", output)

    def test_the_same_forge_twice_is_refused(self):
        output = self.run_gitctap(
            "create", "demo", "--on", "github", "--on", "github", "--dry-run", expect=1
        )
        self.assertIn("twice", output)

    def test_help_mentions_the_new_command(self):
        output = self.run_gitctap("--help")
        self.assertIn("create", output)
        self.assertIn("gitctap create", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
