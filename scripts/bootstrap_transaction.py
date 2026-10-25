"""Filesystem transaction interface pending reviewed bootstrap baseline."""
from contextlib import contextmanager


@contextmanager
def filesystem_transaction(repo_dir, paths):
    """Validate and recover only the caller's exact managed paths."""
    raise NotImplementedError('BOOTSTRAP_TRANSACTION_NOT_IMPLEMENTED')
    yield
