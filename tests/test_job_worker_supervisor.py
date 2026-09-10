"""Mocked local stdlib tests: no workers, Git commands or HTTP requests run."""

import importlib.util
import io
import json
import signal
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager, redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/harvester/job_worker.py'
SPEC = importlib.util.spec_from_file_location('job_worker_supervisor', SOURCE)
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)

SECRET = 'never-print-this-secret'


def config(**changes):
    value = worker.Config(
        'task-1',
        'job-worker-1',
        'https://server.example',
        SECRET,
        60.0,
        False,
        None,
        '/tmp/job-result.json',
    )
    return replace(value, **changes)


class ConfigAndHttpTests(unittest.TestCase):
    def test_environment_validation_does_not_reflect_secrets(self):
        env = {
            'JOB_TASK_ID': 'task-1',
            'JOB_WORKER_NAME': 'worker-1',
            'CODETETHER_SERVER': 'https://server.example',
            'CODETETHER_TOKEN': SECRET,
        }
        self.assertFalse(worker.Config.from_env(env).read_only)
        self.assertNotIn(SECRET, repr(worker.Config.from_env(env)))
        for key, value in [
            ('JOB_DEADLINE_SECONDS', 'nan'),
            ('JOB_DEADLINE_SECONDS', '-1'),
            ('JOB_DEADLINE_SECONDS', 'inf'),
            ('JOB_TASK_ID', '../wrong'),
            ('CODETETHER_SERVER', 'https://user:password@server'),
            ('JOB_READ_ONLY', 'maybe'),
            ('JOB_RESULT_PATH', 'relative'),
        ]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(worker.Diagnostic) as error:
                    worker.Config.from_env({**env, key: value})
                self.assertEqual(
                    str(error.exception), 'job_configuration_invalid'
                )

    def request(self, body, status=200):
        response = Mock(status=status)
        response.read.return_value = body
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(worker, 'build_opener', return_value=opener):
            result = worker.read_status(config(), 3)
        return result, opener

    def test_authenticated_exact_task_get(self):
        result, opener = self.request(
            json.dumps(
                {'id': 'task-1', 'status': 'completed', 'prompt': SECRET}
            ).encode()
        )
        self.assertEqual(result, {'status': 'completed'})
        request = opener.open.call_args.args[0]
        self.assertEqual(
            request.full_url, 'https://server.example/v1/agent/tasks/task-1'
        )
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(
            request.get_header('Authorization'), 'Bearer ' + SECRET
        )
        self.assertIsNone(request.data)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 3)

    def test_bad_response_cannot_supply_success(self):
        for body in (
            b'invalid',
            b'[]',
            b'{"id":"other","status":"completed"}',
            b'{"id":"task-1","status":true}',
            b'{"id":"task-1","status":"unknown"}',
        ):
            with self.subTest(body=body):
                self.assertIn('error', self.request(body)[0])
        with patch.object(worker, 'MAX_RESPONSE', 2):
            self.assertEqual(
                self.request(b'abc')[0]['error'], 'task_poll_response_too_large'
            )

    def test_errors_and_redirects_never_echo_credentials(self):
        for error in (
            TimeoutError(SECRET),
            HTTPError(
                'https://example', 403, SECRET, {}, io.BytesIO(SECRET.encode())
            ),
        ):
            opener = Mock()
            opener.open.side_effect = error
            with patch.object(worker, 'build_opener', return_value=opener):
                result = worker.read_status(config(), 1)
            self.assertNotIn(SECRET, json.dumps(result))
            self.assertIn('error', result)
        self.assertIsNone(
            worker.NoRedirect().redirect_request(
                None, None, 302, '', {}, 'https://other'
            )
        )


class LifecycleTests(unittest.TestCase):
    @contextmanager
    def harness(self, events):
        clock = [0.0]
        handlers = {}
        child = Mock(pid=31415)
        child.wait.return_value = -signal.SIGTERM
        poller = Mock()
        items = iter(events)

        def next_item(timeout):
            clock[0] += timeout
            item = next(items, None)
            return item(handlers, clock) if callable(item) else item

        poller.next.side_effect = next_item
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    worker.time, 'monotonic', side_effect=lambda: clock[0]
                )
            )
            stack.enter_context(
                patch.object(
                    worker.time,
                    'sleep',
                    side_effect=lambda n: clock.__setitem__(0, clock[0] + n),
                )
            )
            stack.enter_context(
                patch.object(
                    worker.signal, 'getsignal', return_value=signal.SIG_DFL
                )
            )
            stack.enter_context(
                patch.object(
                    worker.signal,
                    'signal',
                    side_effect=lambda n, h: handlers.__setitem__(n, h),
                )
            )
            spawn = stack.enter_context(
                patch.object(worker.subprocess, 'Popen', return_value=child)
            )
            stack.enter_context(
                patch.object(worker, 'Poller', return_value=poller)
            )
            peek = stack.enter_context(
                patch.object(worker.os, 'waitid', return_value=None)
            )
            kill = stack.enter_context(patch.object(worker.os, 'killpg'))
            save = stack.enter_context(patch.object(worker, 'write_result'))
            audit = stack.enter_context(
                patch.object(
                    worker,
                    'audit_workspace',
                    return_value={
                        'workspace_clean': True,
                        'unpushed': False,
                        'cleanup_eligible': True,
                        'audit_diagnostic': 'audit_local_refs_only',
                    },
                )
            )
            output = stack.enter_context(redirect_stdout(io.StringIO()))
            yield SimpleNamespace(
                child=child,
                spawn=spawn,
                poller=poller,
                peek=peek,
                kill=kill,
                save=save,
                audit=audit,
                output=output,
            )

    def test_only_confirmed_completed_succeeds_and_audits_after_stop(self):
        with self.harness(
            [{'status': 'running'}, {'status': 'completed'}]
        ) as h:
            h.audit.side_effect = lambda *a: (
                self.assertTrue(h.child.wait.called)
                or {
                    'workspace_clean': True,
                    'unpushed': False,
                    'cleanup_eligible': True,
                }
            )
            self.assertEqual(worker.supervise(config()), 0)
            args, options = h.spawn.call_args.args[0], h.spawn.call_args.kwargs
            self.assertEqual(args[args.index('--name') + 1], 'job-worker-1')
            self.assertEqual(
                args[args.index('--max-concurrent-tasks') + 1], '1'
            )
            self.assertEqual(
                args[args.index('--workspaces') + 1],
                '/var/lib/codetether/repos',
            )
            self.assertEqual(args[args.index('--auto-approve') + 1], 'all')
            self.assertNotIn(SECRET, str(args))
            self.assertTrue(options['start_new_session'])
            self.assertEqual(
                options['env']['CODETETHER_WORKER_TARGETED_ONLY'], '1'
            )
            self.assertEqual(options['env']['HOME'], '/work')
            self.assertEqual(options['stdout'], subprocess.DEVNULL)
            self.assertEqual(
                [c.args for c in h.kill.call_args_list],
                [(31415, signal.SIGTERM), (31415, signal.SIGKILL)],
            )
            self.assertEqual(
                h.save.call_args.args[1]['task_status'], 'completed'
            )
            self.assertNotIn(SECRET, h.output.getvalue())
            h.poller.close.assert_called_once()
            h.child.poll.assert_not_called()

    def test_readonly_success_never_audits_git(self):
        with self.harness([{'status': 'completed'}]) as h:
            self.assertEqual(worker.supervise(config(read_only=True)), 0)
            self.assertEqual(h.spawn.call_args.args[0][-3], 'safe')
            h.audit.assert_not_called()
            self.assertIsNone(h.save.call_args.args[1]['workspace_clean'])

    def test_failed_and_cancelled_tasks_exit_nonzero(self):
        for status in ('failed', 'cancelled'):
            with (
                self.subTest(status=status),
                self.harness([{'status': status}]) as h,
            ):
                self.assertEqual(worker.supervise(config()), 1)
                h.audit.assert_not_called()
                self.assertEqual(
                    h.save.call_args.args[1]['task_status'], status
                )

    def test_poll_errors_are_bounded_and_never_success(self):
        with self.harness(
            [{'error': 'task_poll_http_error', 'http_status': 503}]
        ) as h:
            self.assertEqual(worker.supervise(config(deadline=0.6)), 1)
            result = h.save.call_args.args[1]
            self.assertEqual(result['diagnostic'], 'job_deadline_exceeded')
            self.assertEqual(result['poll_errors'], 1)
            h.audit.assert_not_called()
        with self.harness(
            [{'error': 'task_poll_transport_error'}, {'status': 'completed'}]
        ) as h:
            self.assertEqual(worker.supervise(config()), 0)
            self.assertEqual(h.save.call_args.args[1]['poll_errors'], 1)

    def test_completed_after_deadline_is_rejected(self):
        def late(handlers, clock):
            clock[0] = 70
            return {'status': 'completed'}

        with self.harness([late]) as h:
            self.assertEqual(worker.supervise(config()), 1)
            self.assertEqual(
                h.save.call_args.args[1]['diagnostic'], 'job_deadline_exceeded'
            )

    def test_termination_is_forwarded_to_owned_group(self):
        def interrupt(handlers, clock):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            return {'status': 'completed'}

        with self.harness([interrupt]) as h:
            self.assertEqual(worker.supervise(config()), 143)
            self.assertEqual(
                h.kill.call_args_list[0].args, (31415, signal.SIGTERM)
            )
            h.audit.assert_not_called()

    def test_worker_exit_is_not_task_success(self):
        with self.harness([None]) as h:
            h.peek.return_value = SimpleNamespace(si_pid=31415)
            self.assertEqual(worker.supervise(config()), 1)
            self.assertEqual(
                h.save.call_args.args[1]['diagnostic'],
                'worker_exited_before_terminal_task',
            )

    def test_lost_child_ownership_does_not_signal_any_group(self):
        with self.harness([None]) as h:
            h.peek.side_effect = ChildProcessError(SECRET)
            self.assertEqual(worker.supervise(config()), 1)
            h.kill.assert_not_called()
            self.assertNotIn(SECRET, h.output.getvalue())

    def test_start_and_result_write_failures_are_private(self):
        with self.harness([]) as h:
            h.spawn.side_effect = OSError(SECRET)
            self.assertEqual(worker.supervise(config()), 1)
            self.assertEqual(
                h.save.call_args.args[1]['diagnostic'], 'worker_start_failed'
            )
            h.kill.assert_not_called()
            self.assertNotIn(SECRET, h.output.getvalue())
        with self.harness([{'status': 'completed'}]) as h:
            h.save.side_effect = OSError(SECRET)
            self.assertEqual(worker.supervise(config()), 1)
            self.assertIn('job_result_write_failed', h.output.getvalue())
            self.assertNotIn(SECRET, h.output.getvalue())


class AuditTests(unittest.TestCase):
    def audit(self, overrides=None):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()
            (path / '.git').mkdir()

            def run(args, **kwargs):
                command = args[args.index('-C') + 2 :]
                calls.append((command, kwargs))
                kind = command[0]
                if overrides and kind in overrides:
                    value = overrides[kind]
                    if isinstance(value, Exception):
                        raise value
                    return SimpleNamespace(returncode=0, stdout=value)
                values = {
                    'config': b'',
                    'symbolic-ref': b'refs/heads/main\n',
                    'status': b'',
                    'stash': b'',
                    'rev-list': b'0\n',
                }
                if kind == 'rev-parse':
                    value = (
                        str(path).encode() + b'\n'
                        if command[1] == '--show-toplevel'
                        else b'false\n'
                    )
                elif kind == 'for-each-ref':
                    value = (
                        b'refs/heads/main\nrefs/heads/topic\n'
                        if command[-1] == 'refs/heads'
                        else b'refs/remotes/origin/main\n'
                    )
                else:
                    value = values[kind]
                return SimpleNamespace(returncode=0, stdout=value)

            with patch.object(worker.subprocess, 'run', side_effect=run):
                result = worker.audit_workspace(
                    config(workspace=str(path)),
                    float('inf'),
                    worker.Termination(),
                )
        return result, calls

    def test_clean_evidence_checks_only_local_branches(self):
        result, calls = self.audit()
        self.assertTrue(result['workspace_clean'])
        self.assertFalse(result['unpushed'])
        self.assertTrue(result['stash_empty'])
        self.assertTrue(result['cleanup_eligible'])
        revs = [cmd for cmd, _ in calls if cmd[0] == 'rev-list']
        self.assertEqual(
            revs,
            [
                [
                    'rev-list',
                    '--count',
                    'refs/heads/main',
                    '--not',
                    '--remotes',
                ],
                [
                    'rev-list',
                    '--count',
                    'refs/heads/topic',
                    '--not',
                    '--remotes',
                ],
            ],
        )
        self.assertFalse(
            any('--all' in cmd or 'fetch' in cmd for cmd, _ in calls)
        )
        self.assertTrue(
            all(opts['env']['GIT_NO_LAZY_FETCH'] == '1' for _, opts in calls)
        )

    def test_dirty_stash_unpushed_and_errors_retain_workspace(self):
        for overrides in (
            {'status': b'?? private-file\n'},
            {'stash': b'stash@{0}\n'},
            {'rev-list': b'2\n'},
            {'config': b'filter.secret.clean\n'},
            {'rev-list': subprocess.TimeoutExpired(SECRET, 1)},
        ):
            with self.subTest(keys=list(overrides)):
                result, _ = self.audit(overrides)
                self.assertFalse(result['cleanup_eligible'])
                self.assertNotIn(SECRET, json.dumps(result))
                self.assertNotIn('private-file', json.dumps(result))

    def test_missing_workspace_is_unknown_not_clean(self):
        with patch.object(worker.subprocess, 'run') as run:
            result = worker.audit_workspace(config(), 100, worker.Termination())
        self.assertIsNone(result['workspace_clean'])
        self.assertIsNone(result['unpushed'])
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
