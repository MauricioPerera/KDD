# KDD for Codex

This public plugin supplies the `kdd-workflow` skill.

It does not send data, start services, register hooks, or connect to external
systems. It only provides workflow instructions.

See [privacy](./PRIVACY.md), [terms](./TERMS.md), [support](./SUPPORT.md), and
the [publication checklist](./PUBLISHING.md). A future relay integration must
use a controlled domain, explicit consent, a public privacy policy, and a
separate security review before hooks are reintroduced.

## Install or upgrade to 1.1.0

Register the Git marketplace at the release tag, then install the skill.

```sh
codex plugin marketplace add https://github.com/MauricioPerera/KDD.git --ref kdd-codex-v1.1.0 --sparse .agents/plugins --sparse plugins/kdd-codex
codex plugin add kdd-codex@kdd
codex plugin list --marketplace kdd --json
```

If `kdd` is already configured from a local directory, keep that path for
rollback and run `codex plugin marketplace remove kdd` before registering the
Git source. The listing should report `kdd-codex@kdd` enabled at `1.1.0`.
This upgrade was verified from `1.0.0+codex.20260921005515` in Codex CLI
0.144.1.

The release tag `kdd-codex-v1.1.0` points to
`ef5e1efab8e8cf99bb1060b07afab286f2f63f22`. To install the ZIP, extract it
and run `codex plugin marketplace add <extracted-directory>`, then
`codex plugin add kdd-codex@kdd`. Register the directory that contains
`.agents/plugins/marketplace.json` and `plugins/kdd-codex/`.
[GitHub release](https://github.com/MauricioPerera/KDD/releases/tag/kdd-codex-v1.1.0) ·
[Marketplace ZIP](https://github.com/MauricioPerera/KDD/releases/download/kdd-codex-v1.1.0/kdd-codex-1.1.0-marketplace.zip)

ZIP SHA-256 `736546710edeb0b5ae13db78c6d4b617da83661b292d6ec7601c400ac647ca7e`.

## Adopt validation in a Python project

For a Python repository with existing contracts, a reviewed KDD checkout can
provide the [adoption CLI](https://github.com/MauricioPerera/KDD/blob/3e8bbfaac5e78b61daf2bc5b66985a749bae5f66/tools/kdd-adoption/README.md). The skill guides
a preview and explicit application. The installed project command records the
KDD commit it actually executes.

[Adoption and quality pilot evidence](https://github.com/MauricioPerera/KDD/blob/main/knowledge/piloto-kdd-complemento.md)
