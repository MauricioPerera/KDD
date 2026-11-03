"""Read a committed requirement graph and reuse canonical Task validation.

The report describes the selected commit, not uncommitted files or a new test
execution. Trust and scope are defined in knowledge/requirements-traceability.md.
"""
import hashlib
import json
from pathlib import Path
import re

import task_git as journal
from task_model import TaskError
from traceability_model import exact_path, manifest_spec, parse_plan
from validate_contracts import parse_frontmatter
from validate_tasks import validate_range, validate_snapshot


def _finding(code, message, requirement='', task_id=''):
    return dict(code=code, requirement=requirement, task_id=task_id, message=message)


def _input(message):
    raise ValueError('TRACE_INPUT: ' + message)


def _repository(repo_root):
    root = Path(repo_root).resolve(strict=True)
    actual = Path(journal.git(root, 'rev-parse', '--show-toplevel')).resolve()
    if actual != root:
        _input('repo-root must be the Git working tree root')
    # Missing promisor objects can make otherwise read-only Git commands fetch.
    keys = journal.git(root, 'config', '--list', '--name-only').lower().splitlines()
    if any(re.fullmatch(r'extensions\.partialclone|remote\..*\.promisor', k) for k in keys):
        _input('partial clones are unsupported; provide the required objects locally')
    return root


class _Projection:
    def __init__(self, root, revision, manifest):
        self.root, self.revision, self.manifest = root, revision, manifest
        self.objects, self.plans, self.contracts = {}, {}, {}
        self.findings = []
        self.journal_ok = False

    def blob(self, revision, name):
        name = exact_path(name)
        key = (revision, name)
        if key not in self.objects:
            output = journal.git(self.root, 'ls-tree', '-z', revision, '--', name)
            records = list(filter(None, output.split('\0')))
            if len(records) != 1 or '\t' not in records[0]:
                _input('missing regular Git file: ' + name)
            header, path = records[0].split('\t', 1)
            fields = header.split()
            if path != name or len(fields) != 3 or fields[0] not in ('100644', '100755') or fields[1] != 'blob':
                _input('expected a regular Git blob: ' + name)
            self.objects[key] = journal.blob(self.root, revision, name)
        return self.objects[key]

    def plan(self, revision):
        if revision not in self.plans:
            manifest = self.blob(revision, self.manifest)
            spec = self.blob(revision, manifest_spec(manifest))
            self.plans[revision] = parse_plan(spec, manifest)
        return self.plans[revision]

    def _contract_inputs(self, revision, oracle, target):
        def serial():
            return self.blob(revision, oracle), self.blob(revision, target)

        try:
            first, second = exact_path(oracle), exact_path(target)
        except ValueError:
            return serial()
        if (first == second or first.startswith(second + '/') or second.startswith(first + '/')
                or (revision, first) in self.objects or (revision, second) in self.objects
                or not journal._native_oid(self.root, revision)):
            return serial()
        output = journal.git(self.root, 'ls-tree', '-z', revision, '--', first, second)
        records = {}
        for record in filter(None, output.split('\0')):
            header, separator, path = record.partition('\t')
            fields = header.split()
            if (not separator or path in records or len(fields) != 3
                    or fields[0] not in ('100644', '100755') or fields[1] != 'blob'):
                return serial()
            records[path] = fields[2]
        if set(records) != {first, second}:
            return serial()
        self.objects[(revision, first)] = journal.blob(self.root, revision, first)
        self.objects[(revision, second)] = journal.blob(self.root, revision, second)
        return self.objects[(revision, first)], self.objects[(revision, second)]

    def contract(self, revision, name):
        key = (revision, name)
        if key not in self.contracts:
            metadata, _ = parse_frontmatter(self.blob(revision, name))
            if not isinstance(metadata, dict) or metadata.get('type') != 'Task Contract':
                _input('expected a task contract: ' + name)
            required = ('tests', 'target', 'test_command', 'tests_sha256')
            if not all(isinstance(metadata.get(k), str) and metadata[k] for k in required):
                _input('contract has invalid oracle metadata: ' + name)
            if not re.fullmatch(r'[0-9a-f]{64}', metadata['tests_sha256']):
                _input('contract has an invalid oracle seal: ' + name)
            oracle, _ = self._contract_inputs(revision, metadata['tests'], metadata['target'])
            sealed = hashlib.sha256(oracle.encode('utf-8')).hexdigest() == metadata['tests_sha256']
            self.contracts[key] = metadata, sealed
        return self.contracts[key]

    def tasks(self):
        for name in journal.paths(self.root, self.revision, 'knowledge/tasks'):
            if name.endswith('.md') and Path(name).name != 'index.md':
                self.blob(self.revision, name)
        return journal.read_tasks(self.root, self.revision)

    def _initial_ready(self, task):
        base = task['branch_base']
        before = journal.read_tasks(self.root, base).get(task['task_id'])
        if not before:
            raise TaskError('initial ready task is missing at branch_base')
        expected = {'status': 'ready', 'branch_base': '', 'contract': task['contract'],
                    'approved_ref': task['approved_ref']}
        if any(before.get(k) != v for k, v in expected.items()):
            raise TaskError('branch_base must contain the original approved ready task')
        return base

    def _audit_index(self, base, chain):
        if base in chain:
            return chain.index(base)
        low, high = 0, len(chain) - 1
        if not journal.ancestor(self.root, base, chain[high]):
            raise TaskError('branch_base is not an ancestor of the observed commit')
        # Find the first first-parent commit that imported this start baseline.
        while low < high:
            middle = (low + high) // 2
            if journal.ancestor(self.root, base, chain[middle]):
                high = middle
            else:
                low = middle + 1
        if low == 0:
            raise TaskError('the original journal import is outside available history')
        return low - 1

    def audit(self, tasks, selected):
        audit_base = ''
        started = [tasks[t] for t in sorted(selected) if t in tasks and tasks[t]['branch_base']]
        if not started:
            errors = validate_snapshot(self.root, self.revision)
        else:
            chain = journal.git(self.root, 'rev-list', '--first-parent', '--reverse', self.revision).splitlines()
            try:
                indices = [self._audit_index(self._initial_ready(task), chain) for task in started]
                audit_base = chain[min(indices)]
                # validate_range already checks both endpoints and every transition.
                errors = validate_range(self.root, audit_base, self.revision)
            except (TaskError, ValueError, OSError) as error:
                errors = [str(error)]
        self.journal_ok = not errors
        self.findings.extend(_finding('TRACE_JOURNAL', error) for error in errors)
        return audit_base

    def _approved(self, requirement, task):
        try:
            plan = self.plan(task['approved_ref'])
            expected = next((r for r in plan['requirements'] if r['id'] == requirement['id']), None)
            return expected is not None and expected['fingerprint'] == requirement['fingerprint']
        except (ValueError, OSError):
            return False

    def _fresh(self, task, metadata):
        names = (task['contract'], metadata['tests'], metadata['target'])
        try:
            return all(self.blob(self.revision, p) == self.blob(task['verified_ref'], p) for p in names)
        except (ValueError, OSError):
            return False

    def _stale(self, link, requirement, message):
        link['state'] = 'stale'
        self.findings.append(_finding('TRACE_STALE', message, requirement['id'], link['task_id']))

    def link(self, requirement, binding, task):
        revision = task['verified_ref'] if task and task['status'] == 'done' else self.revision
        metadata, sealed = self.contract(revision, binding['contract'])
        link = dict(contract=binding['contract'], oracle=metadata['tests'], target=metadata['target'],
                    task_id='', task_status='', approved_ref='', branch_tip='', tested_commit='',
                    evidence='', evidence_sha256='', state='pending', historical_verified=False)
        if not sealed:
            self._stale(link, requirement, 'oracle does not match its declared seal')
        if task is None:
            return link
        self._task_fields(link, task)
        if not self.journal_ok or task['contract'] != binding['contract']:
            self._stale(link, requirement, 'canonical journal or task/contract relationship is invalid')
            return link
        if task['status'] == 'done':
            report = json.loads(self.blob(self.revision, task['evidence']))
            link.update(branch_tip=report['branch_tip'], historical_verified=True, state='verified')
            if not self._fresh(task, metadata):
                self._stale(link, requirement, 'contract, target or oracle differs from tested revision')
        if task['approved_ref'] and not self._approved(requirement, task):
            self._stale(link, requirement, 'requirement or bindings differ from the approved revision')
        return link

    @staticmethod
    def _task_fields(link, task):
        for field in ('task_id', 'approved_ref', 'evidence', 'evidence_sha256'):
            link[field] = task[field]
        link['task_status'] = task['status']
        link['tested_commit'] = task['verified_ref']

    def rows(self, requirements, tasks):
        result = []
        for requirement in requirements:
            links = []
            for binding in requirement['bindings']:
                for identifier in binding['tasks'] or ['']:
                    link = self.link(requirement, binding, tasks.get(identifier))
                    if not link['task_id']:
                        link['task_id'] = identifier
                    links.append(link)
            states = {link['state'] for link in links}
            state = 'stale' if 'stale' in states else ('verified' if states == {'verified'} else 'pending')
            result.append(dict(id=requirement['id'], text=requirement['text'], state=state, links=links))
        return result


def _empty(manifest):
    return dict(schema_version=1, ok=False, complete=False, observed_commit='', audit_base='',
                manifest=str(manifest), spec='', requirements=[], findings=[])


def _build(report, root, ref, require_verified):
    projection = _Projection(root, journal.commit_sha(root, ref), exact_path(report['manifest']))
    report['observed_commit'] = projection.revision
    plan = projection.plan(projection.revision)
    report['spec'] = plan['spec']
    tasks = projection.tasks()
    selected = {t for r in plan['requirements'] for b in r['bindings'] for t in b['tasks']}
    report['audit_base'] = projection.audit(tasks, selected)
    report['requirements'] = projection.rows(plan['requirements'], tasks)
    report['complete'] = (projection.journal_ok and bool(report['requirements'])
                          and all(r['state'] == 'verified' for r in report['requirements']))
    if require_verified and not report['complete']:
        projection.findings.append(_finding('TRACE_PENDING', 'all requirements must be current and verified'))
    report['findings'] = sorted(projection.findings, key=lambda f: (f['requirement'], f['task_id'], f['code'], f['message']))
    report['ok'] = not report['findings']
    return report


def build_trace(repo_root, ref, manifest_path, require_verified=False):
    """Derive evidence for a fixed Git revision without executing product code."""
    report = _empty(manifest_path)
    try:
        if not isinstance(ref, str) or not ref or any(ord(c) < 32 for c in ref):
            _input('ref must be a nonempty Git revision')
        if type(require_verified) is not bool:
            _input('require_verified must be boolean')
        with journal.object_cache():
            return _build(report, _repository(repo_root), ref, require_verified)
    except (ValueError, OSError, KeyError, TypeError) as error:
        message = str(error)
        code = message.split(':', 1)[0]
        if code not in ('TRACE_INPUT', 'TRACE_SCHEMA', 'TRACE_SPEC', 'TRACE_GIT'):
            code = 'TRACE_GIT' if isinstance(error, TaskError) else 'TRACE_INPUT'
        report.update(ok=False, complete=False)
        report['findings'].append(_finding(code, message))
        return report
