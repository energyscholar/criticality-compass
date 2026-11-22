# Turning the repository public: the runbook

The owner runs every step. Nothing here is run by a script on its own, and nothing is pushed before step 4. Placeholders: `<private-origin>` (the private bare repository), `<out>` (a new directory), `<gh-remote>` (the GitHub remote of the new repository). No host, user or path is written in this file.

0. Run `release/turn-public-check.sh`. Only rows marked `owner-gated` may be open.
1. In GitHub, Settings, Emails, read the noreply address. If it is `<id>+energyscholar@users.noreply.github.com` and not the older form `energyscholar@users.noreply.github.com`, say so: the one constant in `release/public-rewrite.sh` changes and the rehearsal is run again before step 2.
2. Rewrite a copy, then verify it:
   - `release/public-rewrite.sh --origin <private-origin> --out <out>`
   - `release/public-verify.sh <out> <private-origin>` must exit 0 (checks V1 to V8).
   - Before any push, read the diff for anything private: names, quotes, hosts, paths, secrets.
3. Create `energyscholar/criticality-compass` on GitHub as **private** and empty (no README, licence or .gitignore). The description is the first sentence of `README.md`.
4. Push only `main`: `git -C <out> push <gh-remote> main:main`. No tags, no other branch.
5. Make `main` the default branch. In Settings, Actions: allow. Watch the first `ci` run (four cells: Linux and macOS, Python 3.11 and 3.12). On a private repository macOS minutes count ten times against the free quota; one run is about 320 quota-minutes.
6. When the run is green: Settings, Security, enable private vulnerability reporting; Issues on; Wiki and Discussions off; a branch rule on `main` requiring `ci`.
7. Settings, Danger zone, Change visibility: **Public**.
8. After the flip, in a normal commit: add `[project.urls]` (Homepage, Source, Issues, Changelog, each `https://github.com/energyscholar/criticality-compass`) to `pyproject.toml`, `repository-code` to `CITATION.cff`, and the clone URL to `README.md`.
9. Cutover: archive the private origin read-only. New work starts from the public repository. A branch based after the rewrite is rebased through the commit map at `<out>/filter-repo/commit-map`. Only `main` is public; working branches stay private.

If any step fails, stop. The private origin is never changed by steps 0 to 2, so nothing needs undoing before step 3.
