# Add KDD validation to an existing Python project

The consumer supplies its existing Git history, `knowledge/index.md`, contracts
and tests. The directory passed to the command selects its immediate Markdown
contracts. The validation profile executes contract seals, OKF and each managed
`python-unittest` command. Python 3.11 and Git must be available.

From a reviewed KDD checkout, preview an explicit validator commit.

```text
python scripts/adopt_project.py --repo-root CONSUMER --contracts-dir knowledge/contracts --validator-commit KDD_COMMIT_SHA --plan
```

The JSON plan lists files to create and identical files to keep. Apply the same
plan with `--apply` after reviewing those additions. The three managed paths
are `.kdd/validator.lock`, `.kdd/validate.py` and
`.github/workflows/kdd-validate.yml`. Reapplying identical content preserves
its bytes and timestamps, including a checkout with CRLF line endings.

Run `python .kdd/validate.py` from the consumer root. It fetches the exact KDD
commit from the official repository into private temporary storage and checks
its Git blobs before loading the validators. Its final `KDD_PILOT` line records
the resolved revision and result. Network access is required for this command.

If the consumer has a KDD policy at `quality/product.json` or `quality.json`,
supply its independently approved consumer commit in
`KDD_QUALITY_APPROVED_REF`. The required historical files must be present in
that commit. The workflow receives the reference from the repository variable
with the same name.

A conflicting file, linked ancestor, invalid destination or managed path deleted
locally causes an error before applying changes. Recovery covers ordinary write
failures while a single writer owns the consumer tree. A changed validator pin
requires a reviewed update to the lock.

The [contract](../../knowledge/contracts/reusable-kdd-adoption.md) and
[integration tests](../../tests/test_adopt_project.py) define the installed behavior.
