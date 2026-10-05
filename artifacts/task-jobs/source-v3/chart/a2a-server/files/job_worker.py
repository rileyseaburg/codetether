#!/usr/bin/env python3
"""Finite, targeted Kubernetes Job supervisor (stdlib only, Linux/POSIX).

Worker output stays in CodeTether, not the Job console. The termination result
contains metadata only. Local cleanup evidence never deletes files and does not
prove remote branch state; the controller owns workflow/workspace retention decisions.
"""

import json
import math
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


POLL_SECONDS = 2.0
TICK_SECONDS = 0.2
HTTP_TIMEOUT = 10.0
MAX_RESPONSE = 4 * 1024 * 1024
STOP_GRACE = 5.0
REAP_TIMEOUT = 2.0
GIT_TIMEOUT = 5.0
TERMINAL = {'completed', 'failed', 'cancelled'}
PENDING = {'pending', 'queued', 'assigned', 'running', 'working', 'in_progress'}
IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')


class Diagnostic(Exception):
    """A fixed diagnostic code, never a raw subprocess or HTTP exception."""


@dataclass(frozen=True)
class Config:
    task_id: str
    worker_name: str
    server: str
    token: str = field(repr=False)
    deadline: float
    read_only: bool
    workspace: str | None
    result_path: str

    @classmethod
    def from_env(cls, env):
        """Validate input without reflecting its values in diagnostics."""
        try:
            task, name = env['JOB_TASK_ID'], env['JOB_WORKER_NAME']
            server, token = (
                env['CODETETHER_SERVER'].rstrip('/'),
                env['CODETETHER_TOKEN'],
            )
            seconds = float(env.get('JOB_DEADLINE_SECONDS', '3600'))
            mode = env.get('JOB_READ_ONLY', 'false').lower()
            url = urlsplit(server)
            path = env.get('JOB_RESULT_PATH', '/tmp/job-result.json')
            if not (
                IDENTIFIER.fullmatch(task)
                and IDENTIFIER.fullmatch(name)
                and url.scheme in {'http', 'https'}
                and url.hostname
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment
                and token
                and not any(ord(c) < 32 for c in token + server)
                and math.isfinite(seconds)
                and seconds > 0
                and mode in {'true', 'false'}
                and Path(path).is_absolute()
            ):
                raise ValueError
            return cls(
                task,
                name,
                server,
                token,
                seconds,
                mode == 'true',
                env.get('JOB_WORKSPACE_PATH'),
                path,
            )
        except (KeyError, TypeError, ValueError):
            raise Diagnostic('job_configuration_invalid') from None


class NoRedirect(HTTPRedirectHandler):
    """Do not forward credentials to redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_status(config, timeout):
    """Fetch only the target task's status; never log response/request bodies."""
    try:
        request = Request(
            config.server + '/v1/agent/tasks/' + quote(config.task_id, safe=''),
            headers={
                'Authorization': 'Bearer ' + config.token,
                'Accept': 'application/json',
                'User-Agent': 'CodeTether-Job-Supervisor/1.0',
            },
            method='GET',
        )
        with build_opener(NoRedirect()).open(
            request, timeout=timeout
        ) as response:
            if response.status != 200:
                return {
                    'error': 'task_poll_http_error',
                    'http_status': response.status,
                }
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            return {'error': 'task_poll_response_too_large'}
        data = json.loads(body)
        if not isinstance(data, dict) or data.get('id') != config.task_id:
            return {'error': 'task_poll_identity_invalid'}
        status = data.get('status')
        if not isinstance(status, str) or status not in TERMINAL | PENDING:
            return {'error': 'task_poll_status_invalid'}
        return {'status': status}
    except HTTPError as error:
        code = error.code
        error.close()
        return {'error': 'task_poll_http_error', 'http_status': code}
    except (ValueError, UnicodeError):
        return {'error': 'task_poll_response_invalid'}
    except Exception:
        return {'error': 'task_poll_transport_error'}


class Poller:
    """One daemon thread keeps slow HTTP bodies from defeating the Job deadline.

    Socket timeouts are not whole-response deadlines. Never join this thread or
    create overlapping request threads if one HTTP call is still blocked.
    """

    def __init__(self, config, deadline):
        self.config, self.deadline = config, deadline
        self.stopped = threading.Event()
        self.results = queue.Queue(maxsize=1)

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while not self.stopped.is_set():
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                return
            result = read_status(self.config, min(HTTP_TIMEOUT, remaining))
            if self.stopped.is_set():
                return
            try:
                self.results.put_nowait(result)
            except queue.Full:
                pass
            if self.stopped.wait(POLL_SECONDS):
                return

    def next(self, timeout):
        try:
            return self.results.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self.stopped.set()


class Termination:
    """Record signals; control flow performs bounded child-group shutdown."""

    received = None

    def handle(self, number, frame):
        if self.received is None:
            self.received = number


def child_exited(child):
    """Peek without reaping, keeping PID/PGID reserved until group shutdown."""
    try:
        return (
            os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            is not None
        )
    except (ChildProcessError, OSError):
        raise Diagnostic('worker_ownership_lost') from None


def stop_child(child, number):
    """Never signal arbitrary PIDs: child is our unreaped new-session leader."""
    try:
        child_exited(child)
        try:
            os.killpg(child.pid, number)
        except ProcessLookupError:
            pass
        # Do not reap the leader early: descendants get the full grace interval,
        # and the PGID cannot be recycled before our final group signal.
        end = time.monotonic() + STOP_GRACE
        while time.monotonic() < end:
            time.sleep(max(0, min(TICK_SECONDS, end - time.monotonic())))
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return child.wait(timeout=REAP_TIMEOUT), True
    except Exception:
        return None, False


def audit_workspace(config, deadline, termination):
    """Local, conservative evidence after shutdown; never fetch or delete.

    Detached, shallow, partial, filtered and alternate-object repositories are
    intentionally ineligible. Cached remote refs are not live remote proof.
    """
    result = {
        'workspace_clean': None,
        'stash_empty': None,
        'unpushed': None,
        'cleanup_eligible': False,
        'audit_diagnostic': 'audit_unavailable',
    }
    if not config.workspace:
        return {**result, 'audit_diagnostic': 'audit_workspace_unspecified'}
    try:
        path = Path(config.workspace)
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise Diagnostic('audit_workspace_invalid')
        gd = path / '.git'
        if (
            not gd.is_dir()
            or gd.is_symlink()
            or any(
                p.exists()
                for p in (
                    path / '.gitmodules',
                    gd / 'modules',
                    gd / 'shallow',
                    gd / 'info/grafts',
                    gd / 'objects/info/alternates',
                )
            )
        ):
            raise Diagnostic('audit_git_layout_unsupported')
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(
            {
                'GIT_OPTIONAL_LOCKS': '0',
                'GIT_TERMINAL_PROMPT': '0',
                'GIT_NO_LAZY_FETCH': '1',
                'GIT_NO_REPLACE_OBJECTS': '1',
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_CONFIG_GLOBAL': os.devnull,
                'GIT_CEILING_DIRECTORIES': str(path.parent),
            }
        )

        def git(*args, allowed=(0,)):
            remaining = deadline - time.monotonic()
            if termination.received or remaining <= 0:
                raise Diagnostic('audit_deadline_or_termination')
            run = subprocess.run(
                [
                    'git',
                    '--no-pager',
                    '--no-optional-locks',
                    '-c',
                    'core.fsmonitor=false',
                    '-c',
                    'core.hooksPath=' + os.devnull,
                    '-c',
                    'log.showSignature=false',
                    '-C',
                    str(path),
                    *args,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
                timeout=min(GIT_TIMEOUT, remaining),
                check=False,
            )
            if run.returncode not in allowed or len(run.stdout) > 1024 * 1024:
                raise Diagnostic('audit_git_failed')
            return run.stdout

        if (
            Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve()
            != path
        ):
            raise Diagnostic('audit_workspace_not_root')
        if git(
            'config',
            '--local',
            '--includes',
            '--name-only',
            '--get-regexp',
            r'^(filter\.|remote\..*\.promisor$|extensions\.partialclone$)',
            allowed=(0, 1),
        ):
            raise Diagnostic('audit_filters_or_partial_clone')
        if git('rev-parse', '--is-shallow-repository').strip() != b'false':
            raise Diagnostic('audit_shallow_repository')
        if not git('symbolic-ref', '--quiet', 'HEAD').startswith(
            b'refs/heads/'
        ):
            raise Diagnostic('audit_detached_head')
        clean = not git(
            'status',
            '--porcelain',
            '--untracked-files=normal',
            '--ignore-submodules=none',
        ).strip()
        stash_empty = not git(
            'stash', 'list', '--format=%gd', '--no-show-signature'
        ).strip()
        result['workspace_clean'] = clean and stash_empty
        result['stash_empty'] = stash_empty
        head = git('rev-parse', 'HEAD').decode().strip()
        if not re.fullmatch(r'[0-9a-fA-F]{40,64}', head):
            raise Diagnostic('audit_head_invalid')
        result['head_sha'] = head
        branches = (
            git('for-each-ref', '--format=%(refname)', 'refs/heads')
            .decode()
            .splitlines()
        )
        remotes = git(
            'for-each-ref', '--format=%(refname)', 'refs/remotes'
        ).strip()
        if not branches or not remotes:
            raise Diagnostic('audit_refs_missing')
        unpushed = False
        for branch in branches:
            if not branch.startswith('refs/heads/') or any(
                ord(c) < 32 for c in branch
            ):
                raise Diagnostic('audit_branch_invalid')
            count = git(
                'rev-list', '--count', branch, '--not', '--remotes'
            ).strip()
            if not count.isdigit():
                raise Diagnostic('audit_count_invalid')
            unpushed = unpushed or int(count) > 0
        if termination.received or time.monotonic() >= deadline:
            raise Diagnostic('audit_deadline_or_termination')
        result.update(
            unpushed=unpushed,
            cleanup_eligible=clean and stash_empty and not unpushed,
            audit_diagnostic='audit_local_refs_only',
        )
    except Diagnostic as error:
        result['audit_diagnostic'] = error.args[0]
    except subprocess.TimeoutExpired:
        result['audit_diagnostic'] = 'audit_git_timeout'
    except Exception:
        result['audit_diagnostic'] = 'audit_unavailable'
    return result


def write_result(path, result):
    """Persist metadata only; refuse symlink result destinations."""
    fd = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        output.write(json.dumps(result, sort_keys=True) + '\n')
        output.flush()
        os.fsync(output.fileno())


def supervise(config):
    """Run one worker lifetime; zero means API-confirmed completed, not timeout."""
    deadline = time.monotonic() + config.deadline
    termination, previous = Termination(), {}
    child = poller = None
    worker_log = None
    result = {
        'schema_version': 1,
        'task_status': None,
        'diagnostic': 'supervisor_error',
        'workspace_clean': None,
        'stash_empty': None,
        'unpushed': None,
        'cleanup_eligible': False,
        'audit_diagnostic': 'audit_not_applicable',
        'poll_errors': 0,
        'last_poll_error': None,
        'worker_exit_code': None,
    }
    try:
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGCHLD):
            previous[number] = signal.getsignal(number)
            signal.signal(
                number,
                signal.SIG_DFL
                if number == signal.SIGCHLD
                else termination.handle,
            )
        env = dict(os.environ)
        env.update(
            {
                'CODETETHER_SERVER': config.server,
                'CODETETHER_TOKEN': config.token,
                'CODETETHER_WORKER_TARGETED_ONLY': '1',
                'HOME': '/work',
                'XDG_CONFIG_HOME': '/work/.config',
                'XDG_DATA_HOME': '/work/.local/share',
            }
        )
        if termination.received:
            raise Diagnostic('job_terminated')
        minimum = int(os.getenv('JOB_MIN_FREE_BYTES', '0'))
        if minimum:
            root = Path('/var/lib/codetether/repos')
            root.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(root).free < minimum:
                raise Diagnostic('job_storage_insufficient')
        try:
            # Retained privately on failure; never stream credential-bearing startup logs.
            if os.getenv('JOB_PRIVATE_LOG_PATH'):
                fd = os.open(
                    os.environ['JOB_PRIVATE_LOG_PATH'],
                    os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                    0o600,
                )
                worker_log = os.fdopen(fd, 'wb')
            child = subprocess.Popen(
                [
                    'codetether',
                    'worker',
                    '--server',
                    config.server,
                    '--name',
                    config.worker_name,
                    '--workspaces',
                    '/var/lib/codetether/repos',
                    '--auto-approve',
                    'safe' if config.read_only else 'all',
                    '--max-concurrent-tasks',
                    '1',
                ],
                env=env,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=worker_log
                if worker_log is not None
                else subprocess.DEVNULL,
                stderr=worker_log
                if worker_log is not None
                else subprocess.DEVNULL,
            )
        except Exception:
            raise Diagnostic('worker_start_failed') from None
        poller = Poller(config, deadline)
        poller.start()
        while True:
            if termination.received:
                raise Diagnostic('job_terminated')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Diagnostic('job_deadline_exceeded')
            item = poller.next(min(TICK_SECONDS, remaining))
            if termination.received:
                raise Diagnostic('job_terminated')
            if time.monotonic() >= deadline:
                raise Diagnostic('job_deadline_exceeded')
            if item and 'error' in item:
                result['poll_errors'] += 1
                result['last_poll_error'] = item['error']
                if 'http_status' in item:
                    result['last_http_status'] = item['http_status']
            elif item:
                result['task_status'] = item['status']
                if item['status'] in TERMINAL:
                    result['diagnostic'] = 'task_' + item['status']
                    break
            if child_exited(child):
                raise Diagnostic('worker_exited_before_terminal_task')
    except Diagnostic as error:
        result['diagnostic'] = error.args[0]
    except Exception:
        result['diagnostic'] = 'supervisor_error'
    finally:
        if poller:
            poller.close()
        if child:
            result['worker_exit_code'], stopped = stop_child(
                child, termination.received or signal.SIGTERM
            )
            if not stopped:
                result['diagnostic'] = 'worker_shutdown_unconfirmed'
        if termination.received:
            result.update(
                diagnostic='job_terminated', signal=termination.received
            )
        if result['diagnostic'] == 'task_completed' and not config.read_only:
            result.update(audit_workspace(config, deadline, termination))
        if termination.received:
            result.update(
                diagnostic='job_terminated',
                signal=termination.received,
                cleanup_eligible=False,
            )
        try:
            write_result(config.result_path, result)
        except Exception:
            result.update(
                diagnostic='job_result_write_failed', cleanup_eligible=False
            )
        print(json.dumps(result, sort_keys=True), flush=True)
        if worker_log is not None:
            worker_log.close()
        for number, handler in previous.items():
            signal.signal(number, handler)
    if termination.received:
        return 128 + termination.received
    return 0 if result['diagnostic'] == 'task_completed' else 1


def main():
    """Never print environment values or exception tracebacks."""
    try:
        return supervise(Config.from_env(os.environ))
    except Exception:
        print(
            json.dumps(
                {
                    'schema_version': 1,
                    'task_status': None,
                    'workspace_clean': None,
                    'stash_empty': None,
                    'unpushed': None,
                    'cleanup_eligible': False,
                    'diagnostic': 'job_configuration_invalid',
                }
            )
        )
        return 1


if __name__ == '__main__':
    sys.exit(main())
