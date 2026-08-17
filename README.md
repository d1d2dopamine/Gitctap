<div align="center">

<img src="assets/logo.png" alt="gitctap!" width="420">

<br>

▪

<a href="#english">English</a> · <a href="#russian">Русский</a>

<br>

<b>One local project. Several Git forges. One command.</b>
<br>
terminal · Python 3, no dependencies · nothing destructive, ever

<br><br>

<img src="https://img.shields.io/badge/license-MIT-FF4B33?style=flat-square&labelColor=1c1c1c" alt="MIT licence">
<img src="https://img.shields.io/badge/python-3.8%2B-FF4B33?style=flat-square&labelColor=1c1c1c" alt="Python 3.8+">
<img src="https://img.shields.io/badge/dependencies-none-FF4B33?style=flat-square&labelColor=1c1c1c" alt="No dependencies">
<img src="https://img.shields.io/badge/forges-any-8B7FFF?style=flat-square&labelColor=1c1c1c" alt="Any forge">
<img src="https://img.shields.io/badge/version-0.2.0-8B7FFF?style=flat-square&labelColor=1c1c1c" alt="Version 0.2.0">

<br><br>

<a href="#-install">Install</a>
&nbsp;·&nbsp;
<a href="CHANGELOG.md">Changelog</a>
&nbsp;·&nbsp;
<a href="docs/">Docs</a>

</div>

---

<a id="english"></a>

## 🧩 What it is

gitctap! publishes one local Git repository to several forges at once — GitHub,
Codeberg, GitLab, a Gitea you host yourself, a bare repository on a drive — with one
command:

```console
$ gitctap push
github   ✓
codeberg ✓
gitlab   ✓
```

Git has always been able to do this. It has several remotes, it knows which commits
the other side is missing, and it sends only those. What Git does not have is a way
to keep that list for you and walk it in one go, so people end up either typing three
pushes by hand or writing the same shell alias again in every project.

gitctap is that list and that walk, and nothing else. **It does not replace Git.** It
has no diff engine of its own, no index, no object store, no daemon, no background
sync — every byte that leaves your machine leaves it through `git push`. When a forge
refuses, you get Git's reason under that forge's name, and the forges that accepted
keep what they got.

One file, Python 3, standard library only. Nothing to compile, nothing to update, no
virtualenv, no config format to learn.

The exclamation mark belongs to the name, not to the command: you type `gitctap`.

---

## ⬇️ Install

| Needs | Version |
| --- | --- |
| Python | 3.8+ |
| Git | 2.x, already in `PATH` |
| System | Linux · macOS · WSL |

From a clone:

```sh
git clone https://github.com/d1d2dopamine/gitctap.git
cd gitctap
bash install.sh          # copies one file into ~/.local/bin/gitctap
```

Or the one file, by hand:

```sh
curl -fsSLO https://raw.githubusercontent.com/d1d2dopamine/gitctap/main/gitctap.py
install -Dm755 gitctap.py ~/.local/bin/gitctap
```

Or with pip, from the clone:

```sh
pip install --user .
```

Uninstalling is `bash install.sh --uninstall`, or deleting that one file. The
configuration in `~/.config/gitctap/` is left behind on purpose; delete the folder if
you want it gone.

---

## ⚡ Quick start

Already created the repositories on each forge? Link them with `gitctap setup`. If they do
not exist yet, `gitctap create` makes them on every forge at once — see
[Starting from scratch](#-starting-from-scratch).

```console
$ gitctap setup
? Project name [my-project]:

Add the repositories you already created on each forge.
  setup only links repositories that already exist. To make them, use: gitctap create
  Paste a clone URL (SSH or HTTPS). Press Enter on an empty line when you are done.

? Repository URL #1 (empty to finish): git@github.com:me/my-project.git
? Short name for this forge [github]:
? Repository URL #2 (empty to finish): git@codeberg.org:me/my-project.git
? Short name for this forge [codeberg]:
? Repository URL #3 (empty to finish):

✓ git remote github · git@github.com:me/my-project.git
✓ git remote codeberg · git@codeberg.org:me/my-project.git
✓ configuration saved to ~/.config/gitctap/projects/my-project-1a2b3c4d.json

reachability
github   ✓ reachable, still empty (your first push will fill it)
codeberg ✓ reachable, still empty (your first push will fill it)

? Push branch main to all 2 forges now? [y/N]
```

That last question is the only push `setup` ever makes, and the default answer is no.

From then on the day looks the way it always did, with one line at the end:

```sh
git add .
git commit -m "what changed"
gitctap push
```

---

## 🧰 Commands

| Command | What it does |
| --- | --- |
| `gitctap setup` | Checks Git, offers `git init` if needed, asks for the URL on each forge, writes the configuration, creates matching Git remotes, tests access, and pushes **only** after you say yes. |
| `gitctap create <name> --on …` | Creates the **empty** repository on several forges in one run (GitHub, Codeberg, GitLab, Gitea, Framagit, Salsa, Disroot, or a self-hosted one), private by default, links them as remotes, and then tells you how to publish the content. A repository that already exists is linked, never overwritten. |
| `gitctap push` | Sends the current branch to every configured forge, one after another, and prints a result line per forge. Exit code 1 if any forge refused. |
| `gitctap status` | How far each forge is from your branch: `up to date`, `2 commits behind`, `1 commit ahead of you`, `diverged`, or the reason it could not be reached. |
| `gitctap check` | Git, repository, branch, commits, configuration, remotes, reachability, authorisation — and publishes nothing. |
| `gitctap add <name> [url]` | One more forge for this project. |
| `gitctap remove <name>` | Forgets a forge. **Never touches the repository on that forge.** |
| `gitctap list` | Every configured forge, its host, and whether the local Git remote agrees with the configuration. |

Worth knowing:

- `push --tags` — tags travel only when you ask. Plain `push` sends commits.
- `push --only github` / `push --skip gitlab` — repeatable, for when one forge is down.
- `push --dry-run` — Git says what it would send and sends nothing.
- `status --offline` — compares against what Git already knows, contacts nobody.
- `status --fetch` — fetch first, for exact counts.
- `-C <path>` — work on a project somewhere else.
- `--ascii`, `--no-color`, `NO_COLOR` — for logs and dumb terminals.

Full reference: [`docs/COMMANDS.md`](docs/COMMANDS.md).

---

## 🌱 Starting from scratch

One command, one name, several forges. `create` makes the repositories empty and stops
there: the content stays your decision.

```console
$ gitctap create my-project --on github --on codeberg
gitctap! create · my-project · private 2 forges
  gitctap creates empty repositories. It never overwrites or deletes one that is already there.

→ github · github.com
  ✓ created · git@github.com:me/my-project.git

→ codeberg · codeberg.org
  ✓ created · git@codeberg.org:me/my-project.git

✓ git remote github · git@github.com:me/my-project.git
✓ git remote codeberg · git@codeberg.org:me/my-project.git
✓ configuration saved to ~/.config/gitctap/projects/my-project-4cd57620.json

result
  github   ✓ git@github.com:me/my-project.git
  codeberg ✓ git@codeberg.org:me/my-project.git

! 4 files here are not committed yet, and gitctap never commits for you.
  git add .
  git commit -m "first commit"
  gitctap push
```

If the folder already has commits, the last block says so instead, and offers
`gitctap push` — or do both at once with `gitctap create … --push`.

**Where the authorisation comes from**, in this order:

1. a token in an environment variable: `$GITHUB_TOKEN`, `$CODEBERG_TOKEN`, `$GITEA_TOKEN`,
   `$GITLAB_TOKEN`, or `$GITCTAP_<FORGE>_TOKEN` for one specific forge;
2. the forge's own CLI, if it is installed and already logged in: `gh`, `tea`, `glab`;
3. a hidden one-time prompt, used for that single request.

gitctap never writes a token anywhere. Set `GITCTAP_DISABLE_CLI=1` to skip step 2.

```sh
gitctap create my-project --on github --on codeberg --dry-run  # show the plan, create nothing
gitctap create my-project --on github --public                 # public instead of private
gitctap create my-project --on github --owner my-org           # under an organisation or group
gitctap create my-project --on work=gitea:git.example.org      # self-hosted (gitea, gitlab, github)
gitctap create my-project --on mirror=codeberg                 # a known forge under another short name
```

## 🛡️ Safety

The rule the whole tool is built around:

> **gitctap never deletes anything on a forge, and never rewrites its history, just
> because your local folder looks different.**

What that means in code:

- **No force push.** Not by default, not behind a flag, not at all in this version. A
  rejected push is reported as a rejected push, with the `git pull --rebase` hint next
  to it.
- **`--mirror` is not implemented.** Mirroring can move and delete refs on the other
  side, so it is absent rather than merely switched off.
- **No remote branch deletion, no tag deletion, no remote repository deletion.** There
  is no code path that sends a delete refspec.
- **`remove` edits the configuration only.** The repository on the forge keeps every
  branch, tag and commit; the local Git remote is deleted only if you agree.
- **gitctap never commits for you** and never invents a commit message. Uncommitted
  changes are reported and left alone.
- **No tokens anywhere.** Authorisation is Git's job: SSH keys or your credential
  helper. gitctap stores no secret, reads no secret, prints no secret.
- **Read-only network calls cannot hang.** `status` and `check` run with prompts
  disabled, `ssh -o BatchMode=yes` and a timeout, so they fail out loud instead of
  waiting for input nobody typed.
- **The configuration is the source of truth.** If someone re-pointed a Git remote by
  hand, gitctap pushes to the URL in its configuration and tells you about the
  mismatch instead of quietly using the other one.
- **A partial failure stays partial.** The forges that accepted the push keep their
  commits; nothing is rolled back, nothing is retried with force, and the exit code is
  1 so a script notices.

More: [`docs/SAFETY.md`](docs/SAFETY.md).

---

## 🗂️ Where the configuration lives

Outside the repository, so a published project carries no gitctap files and no list of
your mirrors:

```
~/.config/gitctap/projects/<project>-<hash>.json
```

`XDG_CONFIG_HOME` is honoured, `GITCTAP_CONFIG_DIR` overrides everything, the file is
written `0600`, and it holds nothing but names and URLs:

```json
{
  "gitctap": 1,
  "name": "my-project",
  "path": "/home/me/code/my-project",
  "forges": [
    { "name": "github", "url": "git@github.com:me/my-project.git", "remote": "github" },
    { "name": "codeberg", "url": "git@codeberg.org:me/my-project.git", "remote": "codeberg" }
  ]
}
```

Every forge also becomes an ordinary Git remote with the same name, so the project
stays completely usable without gitctap: `git push codeberg main` works on its own.
Remove gitctap tomorrow and nothing about your repository breaks.

More: [`docs/CONFIG.md`](docs/CONFIG.md).

---

## 🧪 Tests

```sh
python3 -m unittest discover -s tests -v
```

Thirty tests, offline: the "forges" are bare repositories in a temporary folder.
They cover the promises above — that `setup` writes nothing into your repository, that
`push` reports each forge on its own, that a diverged forge is left untouched instead
of forced, that `remove` never loses a commit, and that tags stay home without
`--tags`.

---

## 📚 Docs

[`COMMANDS.md`](docs/COMMANDS.md) ·
[`CONFIG.md`](docs/CONFIG.md) ·
[`SAFETY.md`](docs/SAFETY.md) ·
[`CHANGELOG.md`](CHANGELOG.md)

---

## ⚖️ License

gitctap! is free software under the **MIT License**. The full text is in
[LICENSE](LICENSE).

---

<div align="center">

<img src="assets/logo.png" alt="gitctap!" width="420">

<br>

▪

<a href="#english">English</a> · <a href="#russian">Русский</a>

<br>

<b>Один локальный проект. Несколько Git-площадок. Одна команда.</b>
<br>
терминал · Python 3, без зависимостей · ничего разрушительного, никогда

<br><br>

<a href="#-установка">Установка</a>
&nbsp;·&nbsp;
<a href="CHANGELOG.md">Изменения</a>
&nbsp;·&nbsp;
<a href="docs/">Документация</a>

</div>

---

<a id="russian"></a>

## 🧩 Что это

gitctap! публикует один локальный Git-репозиторий сразу на несколько площадок —
GitHub, Codeberg, GitLab, свою Gitea, bare-репозиторий на диске — одной командой:

```console
$ gitctap push
github   ✓
codeberg ✓
gitlab   ✓
```

Git умел это всегда. У него есть несколько remotes, он сам знает, каких коммитов не
хватает на другой стороне, и отправляет только их. Чего у Git нет — так это списка
площадок, который кто-то держит за тебя и проходит целиком за один раз. Поэтому
люди либо пишут три push руками, либо в каждом новом проекте заново пишут один и тот
же алиас.

gitctap — это тот самый список и тот самый проход, и больше ничего. **Он не заменяет
Git.** У него нет своего сравнения файлов, нет индекса, нет хранилища объектов, нет
демона и фоновой синхронизации: всё, что уходит с твоей машины, уходит через
`git push`. Если площадка отказала — под её именем будет её же причина отказа, а те
площадки, которые приняли, сохраняют то, что получили.

Один файл, Python 3, только стандартная библиотека. Нечего собирать, нечего
обновлять, никакого virtualenv и никакого нового формата конфигов.

Восклицательный знак принадлежит названию, а не команде: набирается `gitctap`.

---

## ⬇️ Установка

| Нужно | Версия |
| --- | --- |
| Python | 3.8+ |
| Git | 2.x, уже в `PATH` |
| Система | Linux · macOS · WSL |

Из клона:

```sh
git clone https://github.com/d1d2dopamine/gitctap.git
cd gitctap
bash install.sh          # копирует один файл в ~/.local/bin/gitctap
```

Или один файл, руками:

```sh
curl -fsSLO https://raw.githubusercontent.com/d1d2dopamine/gitctap/main/gitctap.py
install -Dm755 gitctap.py ~/.local/bin/gitctap
```

Или через pip, из клона:

```sh
pip install --user .
```

Удаление — `bash install.sh --uninstall` или просто удалить этот один файл. Конфиг в
`~/.config/gitctap/` остаётся специально; если он больше не нужен, удали папку.

---

## ⚡ Быстрый старт

Репозитории на площадках уже созданы? Привяжи их через `gitctap setup`. Если их ещё нет,
`gitctap create` создаст их сразу на всех площадках — см.
[Начать с нуля](#-начать-с-нуля).

```console
$ gitctap setup
? Project name [my-project]:

Add the repositories you already created on each forge.
  setup only links repositories that already exist. To make them, use: gitctap create
  Paste a clone URL (SSH or HTTPS). Press Enter on an empty line when you are done.

? Repository URL #1 (empty to finish): git@github.com:me/my-project.git
? Short name for this forge [github]:
? Repository URL #2 (empty to finish): git@codeberg.org:me/my-project.git
? Short name for this forge [codeberg]:
? Repository URL #3 (empty to finish):

✓ git remote github · git@github.com:me/my-project.git
✓ git remote codeberg · git@codeberg.org:me/my-project.git
✓ configuration saved to ~/.config/gitctap/projects/my-project-1a2b3c4d.json

reachability
github   ✓ reachable, still empty (your first push will fill it)
codeberg ✓ reachable, still empty (your first push will fill it)

? Push branch main to all 2 forges now? [y/N]
```

Этот последний вопрос — единственный push, который делает `setup`, и ответ по
умолчанию «нет».

Дальше день выглядит так же, как раньше, только с одной строкой в конце:

```sh
git add .
git commit -m "что изменилось"
gitctap push
```

---

## 🧰 Команды

| Команда | Что делает |
| --- | --- |
| `gitctap setup` | Проверяет Git, предлагает `git init`, если это ещё не репозиторий, спрашивает URL на каждой площадке, сохраняет конфигурацию, создаёт одноимённые Git-remotes, проверяет доступ и делает push **только** после явного согласия. |
| `gitctap create <name> --on …` | Создаёт **пустой** репозиторий сразу на нескольких площадках (GitHub, Codeberg, GitLab, Gitea, Framagit, Salsa, Disroot или свой сервер), по умолчанию приватный, привязывает их как remotes и подсказывает, как выложить содержимое. Уже существующий репозиторий привязывает, но никогда не перезаписывает. |
| `gitctap push` | Отправляет текущую ветку на все настроенные площадки по очереди и печатает результат отдельной строкой на каждую. Код возврата 1, если хоть одна отказала. |
| `gitctap status` | Насколько каждая площадка отстала от твоей ветки: `up to date`, `2 commits behind`, `1 commit ahead of you`, `diverged` — или причина, по которой до неё не дошли. |
| `gitctap check` | Git, репозиторий, ветка, коммиты, конфигурация, remotes, доступность, авторизация — и ничего не публикует. |
| `gitctap add <name> [url]` | Ещё одна площадка к проекту. |
| `gitctap remove <name>` | Убирает площадку из конфигурации. **Удалённый репозиторий не ��рогает вообще.** |
| `gitctap list` | Все настроенные площадки, их хосты и то, совпадает ли локальный Git-remote с конфигурацией. |

Полезное:

- `push --tags` — теги уходят только по просьбе. Обычный `push` отправляет коммиты.
- `push --only github` / `push --skip gitlab` — можно повторять, когда одна площадка лежит.
- `push --dry-run` — Git говорит, что бы он отправил, и не отправляет ничего.
- `status --offline` — сравнение по тому, что Git уже знает, без обращения в сеть.
- `status --fetch` — сначала fetch, чтобы числа были точными.
- `-C <path>` — работать с проектом в другом каталоге.
- `--ascii`, `--no-color`, `NO_COLOR` — для логов и простых терминалов.

Полный справочник: [`docs/COMMANDS.md`](docs/COMMANDS.md).

---

## 🌱 Начать с нуля

Одна команда, одно название, несколько площадок. `create` создаёт репозитории пустыми и
на этом останавливается: содержимое — твоё решение.

```console
$ gitctap create my-project --on github --on codeberg
gitctap! create · my-project · private 2 forges
  gitctap creates empty repositories. It never overwrites or deletes one that is already there.

→ github · github.com
  ✓ created · git@github.com:me/my-project.git

→ codeberg · codeberg.org
  ✓ created · git@codeberg.org:me/my-project.git

✓ git remote github · git@github.com:me/my-project.git
✓ git remote codeberg · git@codeberg.org:me/my-project.git
✓ configuration saved to ~/.config/gitctap/projects/my-project-4cd57620.json

result
  github   ✓ git@github.com:me/my-project.git
  codeberg ✓ git@codeberg.org:me/my-project.git

! 4 files here are not committed yet, and gitctap never commits for you.
  git add .
  git commit -m "first commit"
  gitctap push
```

Если в папке уже есть коммиты, последний блок скажет об этом и предложит `gitctap push` —
или сделай всё сразу: `gitctap create … --push`.

**Откуда берётся авторизация**, в таком порядке:

1. токен из переменной окружения: `$GITHUB_TOKEN`, `$CODEBERG_TOKEN`, `$GITEA_TOKEN`,
   `$GITLAB_TOKEN` или `$GITCTAP_<ПЛОЩАДКА>_TOKEN` для одной конкретной площадки;
2. официальный CLI площадки, если он установлен и в нём уже выполнен вход: `gh`, `tea`, `glab`;
3. скрытый одноразовый ввод токена, только для этого запроса.

gitctap никогда не записывает токен на диск. `GITCTAP_DISABLE_CLI=1` отключает шаг 2.

```sh
gitctap create my-project --on github --on codeberg --dry-run  # показать план, ничего не создавать
gitctap create my-project --on github --public                 # публичный вместо приватного
gitctap create my-project --on github --owner my-org           # в организации или группе
gitctap create my-project --on work=gitea:git.example.org      # свой сервер (gitea, gitlab, github)
gitctap create my-project --on mirror=codeberg                 # известная площадка под другим именем
```

## 🛡️ Безопасность

Правило, вокруг которого собрана вся утилита:

> **gitctap никогда ничего не удаляет на площадке и не перезаписывает её историю
> только потому, что локальная папка выглядит иначе.**

Что это значит в коде:

- **Никакого force push.** Ни по умолчанию, ни под флагом — в этой версии его нет
  вообще. Отказ показывается как отказ, рядом с подсказкой про `git pull --rebase`.
- **`--mirror` не реализован.** Зеркалирование умеет двигать и удалять refs на другой
  стороне, поэтому его просто нет, а не «выключено по умолчанию».
- **Никакого удаления удалённых ветвей, тегов и репозиториев.** В коде нет пути,
  который отправлял бы delete refspec.
- **`remove` меняет только конфигурацию.** Репозиторий на площадке сохраняет все
  ветки, теги и коммиты; локальный Git-remote удаляется только с твоего согласия.
- **gitctap не коммитит за тебя** и не придумывает commit message. Про
  незакоммиченные изменения он сообщает и не трогает их.
- **Никаких токенов нигде.** Авторизация — работа Git: SSH-ключи или credential
  helper. gitctap не хранит, не читает и не печатает секреты.
- **Сетевые запросы на чтение не могут повиснуть.** `status` и `check` работают с
  выключенными промптами, `ssh -o BatchMode=yes` и таймаутом, поэтому падают явно, а
  не ждут ввода, которого никто не сделал.
- **Источник истины — конфигурация.** Если Git-remote кто-то перенастроил руками,
  gitctap отправит на URL из своей конфигурации и скажет про расхождение, а не тихо
  воспользуется чужим адресом.
- **Частичная неудача остаётся частичной.** Площадки, которые приняли push, сохраняют
  коммиты; ничего не откатывается, ничего не повторяется с force, а код возврата 1 —
  чтобы это заметил скрипт.

Подробнее: [`docs/SAFETY.md`](docs/SAFETY.md).

---

## 🗂️ Где лежит конфигурация

Вне репозитория — чтобы в опубликованном проекте не было ни файлов gitctap, ни списка
твоих зеркал:

```
~/.config/gitctap/projects/<project>-<hash>.json
```

`XDG_CONFIG_HOME` учитывается, `GITCTAP_CONFIG_DIR` перебивает всё, файл пишется с
правами `0600`, и внутри только имена и адреса:

```json
{
  "gitctap": 1,
  "name": "my-project",
  "path": "/home/me/code/my-project",
  "forges": [
    { "name": "github", "url": "git@github.com:me/my-project.git", "remote": "github" },
    { "name": "codeberg", "url": "git@codeberg.org:me/my-project.git", "remote": "codeberg" }
  ]
}
```

Каждая площадка становится ещё и обычным Git-remote с тем же именем, так что проект
остаётся полностью рабочим без gitctap: `git push codeberg main` работает сам по себе.
Удали gitctap завтра — в репозитории ничего не сломается.

Подробнее: [`docs/CONFIG.md`](docs/CONFIG.md).

---

## 🧪 Тесты

```sh
python3 -m unittest discover -s tests -v
```

Тридцать тестов, без сети: «площадки» — это bare-репозитории во временной папке.
Они проверяют именно обещания выше: что `setup` ничего не пишет внутрь твоего
репозитория, что `push` отчитывается по каждой площадке отдельно, что разошедшуюся
площадку оставляют в покое, а не форсят, что `remove` не теряет ни одного коммита и
что без `--tags` теги остаются дома.

---

## 📚 Документация

[`COMMANDS.md`](docs/COMMANDS.md) ·
[`CONFIG.md`](docs/CONFIG.md) ·
[`SAFETY.md`](docs/SAFETY.md) ·
[`CHANGELOG.md`](CHANGELOG.md)

---

## ⚖️ Лицензия

gitctap! — свободное программное обеспечение под **лицензией MIT**. Полный текст — в
файле [LICENSE](LICENSE).
