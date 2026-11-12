# Add KDD validation to an existing Python project

The consumer supplies its existing Git history, `knowledge/index.md`, contracts
and tests. The directory passed to the command selects its immediate Markdown
contracts. The validation profile executes contract seals, OKF and each managed
`python-unittest` command. Each contract supplies an explicit `oracle_files`
inventory. Python 3.11, Git and network access to the official KDD repository
are required.

## Install

From a reviewed KDD checkout, preview an explicit validator commit.

```text
python scripts/adopt_project.py --repo-root CONSUMER --contracts-dir knowledge/contracts --validator-commit KDD_COMMIT_SHA --plan
```

Both modes fetch and verify the exact KDD commit before succeeding. The JSON
plan lists files to create and identical files to keep. Apply it with
`--apply` after reviewing the additions. The three managed paths
are `.kdd/validator.lock`, `.kdd/validate.py` and
`.github/workflows/kdd-validate.yml`. Reapplying identical content preserves
its bytes and timestamps, including a checkout with CRLF line endings.
Conflicting files and managed paths deleted locally require review before installation.

Run `python .kdd/validate.py` from the consumer root. It fetches the exact KDD
commit from the official repository into private temporary storage and checks
its Git blobs before loading the validators.

## Prepare Python

For a pure Python project with a `src` layout, add `--source-dir src` to
both the plan and the apply command. For dependencies, add
`--requirements-file requirements-kdd.txt`. The generated launcher uses a
temporary Python 3.11 environment for these options.

List all direct and transitive dependencies as `package==version` with at least
one `--hash=sha256:HEX_DIGEST` per line. Supply hashes for the wheels needed by
Ubuntu and Windows. The manifest accepts comments, continuations,
`--no-index` and `--find-links ./wheels` for a local wheel directory.
Pip checks hashes and accepts binary wheels. Keep build, editable installation,
source distributions and metadata-dependent tests in the consumer's packaging
workflow. Source-directory imports use the consumer checkout.

## Approve the consumer

Review and commit the generated files, selected contracts, oracle inventories
and any wheel manifest. A reviewer records the full consumer commit as the
repository variable `KDD_ADOPTION_APPROVED_REF`. For a matching local run,
pass it explicitly with `python .kdd/validate.py --approved-ref CONSUMER_SHA`.
The CI run checks GitHub's integration commit. It extracts the launcher from
the approved consumer commit, verifies the installed paths and oracle
inventory, and runs two independent managed passes. The `KDD_PILOT` record
reports `adoption_approved_ref`, `verified_kdd_sha`, `oracle_passes` and
`executed_tests` per pass. A launcher with receipt support reports
`oracle_inventory`, the exact case IDs by contract that agreed in both
passes. If the pin lacks receipt support, review a compatible pin before
running the approved profile. Push and manual runs without an adoption
reference retain the one-pass pilot profile.

For a required check, configure branch or organization controls outside the
consumer workflow. A [GitHub organization ruleset](https://docs.github.com/en/rest/orgs/rules#update-an-organization-repository-ruleset)
can require a workflow from a protected repository, path and revision.
If the repository requires checks by job name, also require independent
review for changes to all workflow files and CODEOWNERS, dismiss stale
reviews and restrict bypass permissions. GitHub Actions runs product tests
with read-only repository permissions on Ubuntu and Windows. Product code
executes on the runner, so keep secrets and privileged resources out of these jobs.

For quality, set the independent `KDD_QUALITY_APPROVED_REF` in the local
environment and the repository variable of the same name. The approved commit
must contain exactly one regular policy at `quality/product.json` or
`quality.json`, its protected artifacts and required helpers such as
`scripts/process_tree.py`. Validation checks the policy in HEAD, the index and
the working tree, then delegates its two passes to the pinned quality verifier.
If an older reference lacks a required helper, review and commit the policy,
oracles, helper and inventory together before registering a new reference.

## Review a change

From a trusted checkout with the reviewed launcher and pin, inspect the
committed change between two exact Git SHAs.

```text
python -I .kdd/validate.py review --approved-ref ADOPTION_SHA --base-ref BASE_SHA --candidate-ref CANDIDATE_SHA
```

Use `--small-change` to check the editorial route. Read the diff and project
policy before adding `--editorial-only`. An eligible one-commit correction
returns `lightweight`. Changes to guarantees require the contract and baseline
process.

Use `--review FILE` to check the independent review record for the candidate.
An incomplete record returns exit 1 and `review_ready: false`. Check
`verified_kdd_sha` against the lock and present a ready record with the exact
SHA for human approval. [Risk review protocol](../../knowledge/baseline-risk-review.md)

## Change or roll back the pin

Use the same contract and preparation options that created the installation.
Preview the update with both full KDD commits.

```text
python scripts/adopt_project.py --repo-root CONSUMER --contracts-dir knowledge/contracts --expected-validator-commit OLD_SHA --validator-commit NEW_SHA --plan
```

The plan lists only `.kdd/validator.lock` under `update`. Apply it with
`--apply` after review. Swap the two SHAs to roll back. An unexpected old
pin or a partial installation blocks the change. The installer updates the
lock atomically while a single writer owns the consumer tree.

For an older launcher or workflow template, generate the current managed
files in a separate clean consumer checkout and review the template migration
as its own change. Review and register any new consumer baseline before
relying on the updated protected files in CI.

The [contract](../../knowledge/contracts/reusable-kdd-adoption.md) and
[integration tests](../../tests/test_adoption_trusted_pr.py) define the installed behavior.
