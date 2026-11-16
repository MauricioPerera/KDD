"""Replay the complete init command for the reviewed PR 196 tree."""

SOURCE_SHA = '088225c2ff241b773353825f45c9e63a57861173'
SOURCE_TREE = '71e569b721d4f7785c3b8159a8befcdc06eaceed'
RUNTIME_SHA = '74d357f7099651b9b39dc8088f725183a672ec94'
BASELINE_SHA = '47afa8d45e6139e4ce8939fd4e8f07d65f85f7cb'
INIT_COMMAND = 'python -m unittest tests/test_init_project.py'


def check_checkout(source, sha, tree):
    raise NotImplementedError('replay checkout validation is pending')


def replay(source, bundle, env, timeout=600):
    raise NotImplementedError('isolated replay is pending')
