"""Small local CLI for OKF tasks whose official states are committed on main."""
import argparse
import json
from pathlib import Path
import sys

import task_git as journal
from task_model import TaskError, render_task, task_path


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    subcommands = parser.add_subparsers(dest='command', required=True)
    commands = {}
    for name in ('create', 'ready', 'start', 'block', 'resume', 'finish', 'list', 'show', 'history'):
        command = subcommands.add_parser(name)
        command.add_argument('--json', action='store_true', help='print structured JSON')
        if name != 'list':
            command.add_argument('task_id')
        commands[name] = command
    for name in ('title', 'description', 'contract'):
        commands['create'].add_argument('--' + name, required=True)
    commands['create'].add_argument('--depends-on', action='append', default=[])
    commands['ready'].add_argument('--approved-ref', required=True)
    commands['start'].add_argument('--assignee', required=True)
    for name in ('block', 'resume'):
        commands[name].add_argument('--reason', required=True)
    return parser


def _query(root, args):
    tasks = journal.read_tasks(root)
    if args.command == 'list':
        return [tasks[key] for key in sorted(tasks)]
    task_path(args.task_id)
    if args.task_id not in tasks:
        raise TaskError('TASK_MISSING: ' + args.task_id)
    if args.command == 'history':
        return journal.history(root, args.task_id)
    return tasks[args.task_id]


def _print(result, args):
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return
    for line in _text_lines(result, args):
        print(line)


def _text_lines(result, args):
    if args.command == 'show':
        data, body = journal.read_nodes(Path(args.repo_root).resolve())[args.task_id]
        return [render_task(data, body)]
    if args.command == 'list':
        return ['{}  {:18}  {}  {}'.format(t['task_id'], t['status'], t['assignee'] or '-', t['title']) for t in result]
    if args.command == 'history':
        return ['{}  {:18}  {}'.format(t['commit'][:12], t['status'], t['reason']) for t in result]
    return ['{}: {} ({})'.format(result['task']['task_id'], result['task']['status'], result['commit'])]


def main(argv=None):
    args = _parser().parse_args(argv)
    root = Path(args.repo_root).resolve()
    try:
        if args.command in ('list', 'show', 'history'):
            result = _query(root, args)
        else:
            options = {key: value for key, value in vars(args).items()
                       if key not in ('command', 'task_id', 'repo_root', 'json')}
            result = journal.mutate(root, args.command, args.task_id, options)
        _print(result, args)
        return 0
    except (TaskError, OSError, ValueError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
