# KDD for Codex

This public plugin supplies the `kdd-workflow` skill.

It does not send data, start services, register hooks, or connect to external
systems. It only provides workflow instructions.

See [privacy](./PRIVACY.md), [terms](./TERMS.md), [support](./SUPPORT.md), and
the [publication checklist](./PUBLISHING.md). A future relay integration must
use a controlled domain, explicit consent, a public privacy policy, and a
separate security review before hooks are reintroduced.

## Install or upgrade to 1.2.0

Register the Git marketplace at the versioned release tag and install the skill.
If `kdd` is already registered, remove that marketplace entry before registering
it with the new tag. Keep the previous source and ref for rollback.

```sh
codex plugin marketplace add https://github.com/MauricioPerera/KDD.git --ref kdd-codex-v1.2.0 --sparse .agents/plugins --sparse plugins/kdd-codex
codex plugin add kdd-codex@kdd
codex plugin list --marketplace kdd --json
```

The listing should show `kdd-codex@kdd` enabled at `1.2.0`. For ZIP installation,
verify the SHA-256 in the release notes, extract the archive and register the
directory containing `.agents/plugins/marketplace.json` and `plugins/kdd-codex/`.
For a package rollback, register `kdd-codex-v1.1.0` again and reinstall the skill.
[Previous release](https://github.com/MauricioPerera/KDD/releases/tag/kdd-codex-v1.1.0)

## Upgrade an existing Python project

The reviewed validator for 1.2.0 is
[`144168d168410c28315f07d53e87638a4a10b81c`](https://github.com/MauricioPerera/KDD/tree/144168d168410c28315f07d53e87638a4a10b81c).
Installing the skill and updating a project's validator are separate operations.
The project selects its validator in `.kdd/validator.lock`.

If the project still uses the 1.1.0 launcher or workflow, generate the current
managed files in a disposable clean checkout and review the launcher and
workflow migration. The installer checks for conflicts before updating a pin.
Once the templates match, preview the update with the current and new full
SHAs using `--expected-validator-commit` and `--validator-commit`. Apply the
reviewed plan and commit the changes. See the [versioned adoption guide](https://github.com/MauricioPerera/KDD/blob/144168d168410c28315f07d53e87638a4a10b81c/tools/kdd-adoption/README.md).

Have a reviewer approve the consumer commit for the PR workflow and register its
full SHA as `KDD_ADOPTION_APPROVED_REF`. Review and register a quality reference
separately if the project's protected files changed. To validate from Codex or
the terminal, run `python .kdd/validate.py --approved-ref CONSUMER_SHA` from the
consumer root with the same quality reference in the environment. Compare the
full `verified_kdd_sha` and `oracle_passes` in each `KDD_PILOT` record with the
GitHub Actions results. To roll back a pin, reverse the two SHAs in the installer
and review the resulting consumer commit before changing any approval references.

## Adopt validation in a Python project

For a Python repository with existing contracts, a reviewed KDD checkout can
provide the adoption CLI. The [repository guide](https://github.com/MauricioPerera/KDD/blob/main/tools/kdd-adoption/README.md)
covers the approved consumer reference for pull requests, optional Python
preparation, the quality reference and explicit pin rollback. The installed
project command records the KDD commit it executes.

[Adoption and quality pilot evidence](https://github.com/MauricioPerera/KDD/blob/main/knowledge/piloto-kdd-complemento.md)
