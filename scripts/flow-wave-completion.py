#!/usr/bin/env python3
"""Assignment-bound receipts and finite deadline recovery for /flow:wave.

The coordinator owns assignment state. Receipt stores implement get/put by an
opaque key; FLOW_WAVE_RECEIPT_ADAPTER selects an external JSON argv adapter.
The default filesystem store requires an explicitly shared --state-root.
Messages are wake hints only. This helper schedules nothing and probes no PID.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# NEGATIVE-CONTROL: controls/flow-wave-completion
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
OUTCOMES = {'succeeded', 'failed', 'cancelled'}


class Unknown(Exception):
    """Evidence unavailable or malformed; never a successful completion."""


class Refused(Exception):
    """A known conflicting state cannot be replaced."""


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() != timedelta(0):
            raise ValueError
        return result.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError):
        raise Unknown('timestamp must be an aware UTC datetime') from None


def stamp(value: datetime) -> str:
    return value.isoformat().replace('+00:00', 'Z')


def identity(args: argparse.Namespace) -> dict:
    for value in (args.wave, args.role, args.assignment_id):
        if not TOKEN.fullmatch(value):
            raise Unknown('invalid wave, role or assignment identifier')
    if args.generation < 1:
        raise Unknown('generation must be positive')
    return {'wave':args.wave, 'role':args.role, 'assignment_id':args.assignment_id, 'generation':args.generation}


def key_for(subject: dict) -> str:
    encoded = json.dumps(subject, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'v1-' + hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError, UnicodeError):
        raise Unknown('stored evidence unreadable or malformed') from None


def atomic_write(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, sort_keys=True)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Unknown('state lock unavailable') from None
                time.sleep(.02)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate_receipt(value: Any, subject: dict) -> dict:
    if (not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1
            or not isinstance(value.get('identity'), dict)
            or type(value['identity'].get('generation')) is not int or value.get('identity') != subject
            or value.get('outcome') not in OUTCOMES
            or not isinstance(value.get('evidence'), str) or len(value['evidence']) > 4096):
        raise Unknown('receipt malformed or belongs to another assignment/generation')
    timestamp(value.get('finished_at'))
    return value


def same_result(left: dict, right: dict) -> bool:
    return all(left.get(field) == right.get(field) for field in ('schema','identity','outcome','evidence'))


class FileStore:
    """Immutable receipts; absent files alone mean known absence."""

    def __init__(self, root: Path):
        self.root = root / 'receipts'

    def get(self, key: str) -> dict | None:
        path = self.root / (key + '.json')
        try:
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                raise Unknown('receipt store contains malformed evidence')
            return value
        except FileNotFoundError:
            # A broken store path is unreadable, not established absence.
            if path.is_symlink() or self.root.is_symlink():
                raise Unknown('receipt store unavailable') from None
            return None
        except (OSError, ValueError, UnicodeError):
            raise Unknown('receipt store unavailable or malformed') from None

    def put(self, key: str, receipt: dict) -> dict:
        with locked(self.root / (key + '.lock')):
            existing = self.get(key)
            if existing is not None:
                if not same_result(existing, receipt):
                    raise Refused('terminal receipt already records a different result')
                return existing
            atomic_write(self.root / (key + '.json'), receipt)
            return receipt


class AdapterStore:
    """External executable protocol: argv + [get|put, key], no shell.

    get has empty stdin, put receives {key, receipt} JSON. Both return exactly
    {key, receipt} JSON; get may return receipt=null for known absence. A put
    must durably and immutably publish before replying, with idempotent retries.
    The adapter owns shared accessibility and concurrent immutable put semantics.
    """

    def __init__(self, configured: str):
        try:
            self.argv = json.loads(configured)
            self.timeout = float(os.environ.get('FLOW_WAVE_RECEIPT_TIMEOUT', '10'))
            if (not isinstance(self.argv, list) or not self.argv
                    or any(not isinstance(item, str) or not item for item in self.argv)
                    or not math.isfinite(self.timeout) or not .05 <= self.timeout <= 60):
                raise ValueError
        except (TypeError, ValueError):
            raise Unknown('receipt adapter configuration invalid') from None

    def invoke(self, verb: str, key: str, receipt: dict | None = None):
        process = None
        try:
            process = subprocess.Popen([*self.argv, verb, key], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, text=True, start_new_session=True)
            output, _ = process.communicate(json.dumps({'key':key, 'receipt':receipt}) if verb == 'put' else '',
                                            timeout=self.timeout)
            if process.returncode or len(output) > 1024 * 1024:
                raise Unknown('receipt adapter failed')
            value = json.loads(output)
            if not isinstance(value, dict) or set(value) != {'key','receipt'} or value['key'] != key:
                raise Unknown('receipt adapter returned another key or malformed response')
            return value['receipt']
        except subprocess.TimeoutExpired:
            raise Unknown('receipt adapter timed out') from None
        except (OSError, ValueError, UnicodeError):
            raise Unknown('receipt adapter unavailable or malformed') from None
        finally:
            if process is not None:
                # Also terminate descendants after a timeout or an early parent
                # exit. Detached adapter work must not outlive its request.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()

    def get(self, key: str) -> dict | None:
        return self.invoke('get', key)

    def put(self, key: str, receipt: dict) -> dict:
        value = self.invoke('put', key, receipt)
        if not isinstance(value, dict) or not same_result(value, receipt):
            raise Unknown('receipt adapter did not confirm the requested terminal result')
        return value


def state_root(args: argparse.Namespace) -> Path:
    if not args.state_root:
        raise Unknown('explicit coordinator-visible state-root required')
    try:
        root = Path(args.state_root)
        if not root.is_absolute() or not root.is_dir():
            raise Unknown('state-root must be an existing absolute directory')
        return root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Unknown('state-root unavailable') from None


def store_for(root: Path):
    configured = os.environ.get('FLOW_WAVE_RECEIPT_ADAPTER', '')
    return AdapterStore(configured) if configured else FileStore(root)


def validate_assignment(value: Any, subject: dict) -> dict:
    if (not isinstance(value, dict) or value.get('schema') != 1 or value.get('identity') != subject
            or type(value.get('extensions')) is not int or value['extensions'] not in (0,1)
            or type(value.get('extension_seconds')) is not int or not 1 <= value['extension_seconds'] <= 86400):
        raise Unknown('assignment state malformed or not current')
    timestamp(value.get('initial_deadline'))
    timestamp(value.get('deadline'))
    return value


def execute(args: argparse.Namespace) -> tuple[int, dict]:
    subject = identity(args)
    root = state_root(args)
    key = key_for(subject)
    store = store_for(root)
    now = timestamp(args.now) if args.now else datetime.now(timezone.utc)
    if args.verb == 'complete':
        receipt = {'schema':1, 'identity':subject, 'outcome':args.outcome,
                   'finished_at':stamp(timestamp(args.finished_at)) if args.finished_at else stamp(now),
                   'evidence':args.evidence}
        validate_receipt(receipt, subject)
        previous = store.get(key)
        if previous is not None:
            previous = validate_receipt(previous, subject)
            if not same_result(previous, receipt):
                raise Refused('terminal receipt already records a different result')
            receipt = previous
        result = validate_receipt(store.put(key, receipt), subject)
        observed = validate_receipt(store.get(key), subject)
        if observed != result:
            raise Unknown('published receipt readback did not match')
        return 0, {'status':'recorded', 'key':key, 'receipt':result}
    path = root / subject['wave'] / 'assignments' / (subject['role'] + '.json')
    with locked(path.with_suffix('.lock')):
        try:
            current = json.loads(path.read_text())
            if not isinstance(current, dict):
                raise Unknown('assignment state malformed')
        except FileNotFoundError:
            if path.is_symlink():
                raise Unknown('assignment state unavailable') from None
            current = None
        except (OSError, ValueError, UnicodeError):
            raise Unknown('assignment state unreadable') from None
        if args.verb == 'assign':
            deadline = stamp(timestamp(args.deadline))
            if not 1 <= args.extension_seconds <= 86400:
                raise Unknown('extension-seconds must be between 1 and 86400')
            if current is not None:
                existing = current.get('identity') if isinstance(current, dict) else None
                if not isinstance(existing, dict) or type(existing.get('generation')) is not int:
                    raise Unknown('existing assignment state malformed')
                validate_assignment(current, existing)
                if (existing.get('wave') != subject['wave'] or existing.get('role') != subject['role']
                        or not isinstance(existing.get('assignment_id'), str)
                        or not TOKEN.fullmatch(existing['assignment_id']) or existing['generation'] < 1):
                    raise Unknown('existing assignment belongs to another role or is malformed')
                if existing == subject:
                    if (current['initial_deadline'] != deadline
                            or current['extension_seconds'] != args.extension_seconds):
                        raise Refused('assignment retry cannot change its deadline policy')
                    return 0, {'status':'assigned', **current, 'key':key}
                if subject['generation'] <= existing['generation']:
                    raise Refused('new assignment requires a later generation')
            if timestamp(deadline) <= now:
                raise Refused('new assignment deadline must be in the future')
            current = {'schema':1, 'identity':subject, 'initial_deadline':deadline, 'deadline':deadline,
                       'extension_seconds':args.extension_seconds, 'extensions':0}
            atomic_write(path, current)
            return 0, {'status':'assigned', **current, 'key':key}
        current = validate_assignment(current, subject)
        receipt = store.get(key)
        if receipt is not None:
            receipt = validate_receipt(receipt, subject)
            if timestamp(receipt['finished_at']) > now:
                raise Unknown('receipt completion timestamp is in the future')
            return (0 if receipt['outcome'] == 'succeeded' else 1), {
                'status':'complete', 'outcome':receipt['outcome'], 'receipt':receipt, 'key':key}
        if now < timestamp(current['deadline']):
            return 4, {'status':'waiting', 'deadline':current['deadline'], 'key':key}
        if current['extensions']:
            return 3, {'status':'escalated', 'outcome':'unknown',
                       'reason':'receipt absent after one extension', 'key':key}
        fresh_alive = (args.liveness == 'alive' and args.observed_at is not None
                       and timedelta(0) <= now - timestamp(args.observed_at) <= timedelta(seconds=60))
        if not fresh_alive:
            raise Unknown('receipt absent at deadline; role gone, unknown or liveness not freshly established')
        current['extensions'] = 1
        current['deadline'] = stamp(now + timedelta(seconds=current['extension_seconds']))
        atomic_write(path, current)
        return 4, {'status':'extended', 'deadline':current['deadline'], 'extensions':1, 'key':key}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verb', choices=('assign','complete','check'))
    parser.add_argument('--state-root', default=os.environ.get('FLOW_WAVE_COMPLETION_ROOT'))
    for name in ('wave','role','assignment-id'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--generation', required=True, type=int)
    parser.add_argument('--now', help='explicit UTC clock for offline replay; defaults to current UTC')
    parser.add_argument('--deadline')
    parser.add_argument('--extension-seconds', type=int, default=600)
    parser.add_argument('--outcome', choices=sorted(OUTCOMES))
    parser.add_argument('--finished-at')
    parser.add_argument('--evidence', default='')
    parser.add_argument('--liveness', choices=('alive','gone','unknown'), default='unknown')
    parser.add_argument('--observed-at', help='UTC time of assignment-bound liveness observation, at most 60s old')
    parser.add_argument('--message-arrived', action='store_true', help='wake hint only; never completion evidence')
    args = parser.parse_args(argv)
    try:
        if args.verb == 'assign' and args.deadline is None or args.verb == 'complete' and args.outcome is None:
            raise Unknown('assign requires --deadline; complete requires --outcome')
        code, result = execute(args)
    except Refused as exc:
        code, result = 1, {'status':'refused', 'reason':str(exc)}
    except Unknown as exc:
        code, result = 3, {'status':'unknown', 'reason':str(exc)}
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        code, result = 3, {'status':'unknown', 'reason':'completion state or store unavailable or malformed'}
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
