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
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# NEGATIVE-CONTROL: controls/flow-wave-completion
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
OUTCOMES = {'succeeded', 'failed', 'cancelled'}
MAX_GENERATION = 2**53 - 1
CLOCK_SKEW_SECONDS = 5
UTC_TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z')


class Unknown(Exception):
    """Evidence unavailable or malformed; never a successful completion."""


class Refused(Exception):
    """A known conflicting state cannot be replaced."""


def timestamp(value: str) -> datetime:
    try:
        if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
            raise ValueError
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() != timedelta(0):
            raise ValueError
        return result.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError):
        raise Unknown('timestamp must be an aware UTC datetime') from None


def stamp(value: datetime) -> str:
    return value.isoformat().replace('+00:00', 'Z')


def validate_identity(subject: Any) -> dict:
    if (not isinstance(subject, dict) or set(subject) != {'wave','role','assignment_id','generation'}
            or any(not isinstance(subject.get(field), str) or not TOKEN.fullmatch(subject[field])
                   for field in ('wave','role','assignment_id'))
            or type(subject.get('generation')) is not int or not 1 <= subject['generation'] <= MAX_GENERATION):
        raise Unknown('invalid wave/role/assignment identity or generation outside 1..2^53-1')
    return subject


def identity(args: argparse.Namespace) -> dict:
    return validate_identity({'wave':args.wave, 'role':args.role,
                              'assignment_id':args.assignment_id, 'generation':args.generation})


def key_for(subject: dict) -> str:
    encoded = json.dumps(subject, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'v1-' + hashlib.sha256(encoded).hexdigest()


def strict_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Unknown('duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise Unknown('non-finite JSON number')
    def floating(value):
        result = float(value)
        if not math.isfinite(result):
            raise Unknown('non-finite JSON number')
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)


def read_json(path: Path) -> Any:
    try:
        return strict_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise Unknown('stored evidence unreadable or malformed') from None


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_mkdir(path: Path) -> None:
    if path.is_dir():
        return
    durable_mkdir(path.parent)
    try:
        path.mkdir()
    except FileExistsError:
        if not path.is_dir():
            raise Unknown('state directory unavailable') from None
    sync_directory(path.parent)


def atomic_write(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, sort_keys=True, allow_nan=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
        sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def locked(path: Path, *, create_parent: bool = True):
    if create_parent:
        durable_mkdir(path.parent)
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
    if (not isinstance(value, dict) or set(value) != {'schema','identity','outcome','finished_at','evidence'}
            or type(value.get('schema')) is not int or value['schema'] != 1
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
        self.marker = root / '.receipt-store.json'

    def available(self):
        if self.root.is_symlink() or not self.root.is_dir() or read_json(self.marker) != {'schema':1}:
            raise Unknown('receipt store unavailable')

    def initialize(self):
        with locked(self.marker.with_suffix('.lock'), create_parent=False):
            try:
                self.marker.stat()
            except FileNotFoundError:
                if self.marker.is_symlink() or self.root.is_symlink():
                    raise Unknown('receipt store unavailable') from None
                durable_mkdir(self.root)
                atomic_write(self.marker, {'schema':1})
            self.available()

    def get(self, key: str) -> dict | None:
        self.available()
        path = self.root / (key + '.json')
        try:
            value = strict_json(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise Unknown('receipt store contains malformed evidence')
            # A prior writer may have renamed successfully but failed its
            # directory sync. Neither retries nor readers may acknowledge it
            # until the directory entry is known to be synchronized.
            sync_directory(self.root)
            return value
        except FileNotFoundError:
            # A broken store path is unreadable, not established absence.
            self.available()
            if path.is_symlink():
                raise Unknown('receipt store unavailable') from None
            return None
        except (OSError, ValueError, UnicodeError):
            raise Unknown('receipt store unavailable or malformed') from None

    def put(self, key: str, receipt: dict) -> dict:
        self.available()
        with locked(self.root / (key + '.lock'), create_parent=False):
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
            self.argv = strict_json(configured)
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
                                       stderr=subprocess.DEVNULL, text=True, encoding='utf-8', start_new_session=True)
            payload = (json.dumps({'key':key, 'receipt':receipt}, separators=(',', ':'), allow_nan=False)
                       if verb == 'put' else '')
            output, _ = process.communicate(payload, timeout=self.timeout)
            if process.returncode or len(output) > 1024 * 1024:
                raise Unknown('receipt adapter failed')
            value = strict_json(output)
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
    assigned = timestamp(value.get('assigned_at'))
    initial = timestamp(value.get('initial_deadline'))
    current = timestamp(value.get('deadline'))
    if (initial <= assigned or type(value.get('schema')) is not int
            or type(value['identity'].get('generation')) is not int
            or value['extensions'] == 0 and current != initial
            or value['extensions'] == 1 and current <= initial):
        raise Unknown('assignment deadline/extension history inconsistent')
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
    history = root / '.assigned-roles' / subject['wave'] / (subject['role'] + '.json')
    history_value = {'schema':1, 'identity':subject}
    with locked(path.with_suffix('.lock')):
        try:
            seen = strict_json(history.read_text(encoding="utf-8"))
            if (not isinstance(seen, dict) or set(seen) != {'schema','identity'}
                    or type(seen.get('schema')) is not int or seen['schema'] != 1):
                raise Unknown('assignment history malformed')
            prior = validate_identity(seen['identity'])
            if prior['wave'] != subject['wave'] or prior['role'] != subject['role']:
                raise Unknown('assignment history belongs to another role')
        except FileNotFoundError:
            if history.is_symlink():
                raise Unknown('assignment history unavailable') from None
            seen = None
        except (OSError, ValueError, UnicodeError):
            raise Unknown('assignment history unreadable') from None
        try:
            current = strict_json(path.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                raise Unknown('assignment state malformed')
        except FileNotFoundError:
            if path.is_symlink():
                raise Unknown('assignment state unavailable') from None
            current = None
        except (OSError, ValueError, UnicodeError):
            raise Unknown('assignment state unreadable') from None
        if seen is None and current is not None:
            raise Unknown('assignment history missing; cannot reset deadline or extension budget')
        if seen is not None and (current is None or current.get('identity') != seen['identity']):
            if current is not None:
                prior_state = validate_assignment(current, validate_identity(current.get('identity')))
                if prior_state['identity']['generation'] >= seen['identity']['generation']:
                    raise Unknown('assignment state/history inconsistent')
            if args.verb != 'assign' or subject['generation'] <= seen['identity']['generation']:
                raise Unknown('assignment publication interrupted; recovery requires a strictly higher generation')
            current = None
        if not args.now:
            now = datetime.now(timezone.utc)
        if args.verb == 'assign':
            if isinstance(store, FileStore):
                store.initialize()
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
                        or not TOKEN.fullmatch(existing['assignment_id'])
                        or not 1 <= existing['generation'] <= MAX_GENERATION):
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
            current = {'schema':1, 'identity':subject, 'assigned_at':stamp(now),
                       'initial_deadline':deadline, 'deadline':deadline,
                       'extension_seconds':args.extension_seconds, 'extensions':0}
            if seen != history_value:
                durable_mkdir(history.parent)
                atomic_write(history, history_value)
            atomic_write(path, current)
            return 0, {'status':'assigned', **current, 'key':key}
        current = validate_assignment(current, subject)
        receipt = store.get(key)
        if not args.now:
            now = datetime.now(timezone.utc)
        if receipt is not None:
            receipt = validate_receipt(receipt, subject)
            finished = timestamp(receipt['finished_at'])
            if finished < timestamp(current['assigned_at']) - timedelta(seconds=CLOCK_SKEW_SECONDS):
                raise Unknown('receipt completion predates this assignment')
            if finished > now + timedelta(seconds=CLOCK_SKEW_SECONDS):
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
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        code, result = 3, {'status':'unknown', 'reason':'completion state or store unavailable or malformed'}
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    # Installed helpers report their own status after diagnostics and flushing,
    # so a pipe cannot replace it with the status of tail/head (#1031).
    _code = 3
    try:
        _code = main()
    except SystemExit as _exc:
        _code = _exc.code if isinstance(_exc.code, int) else int(bool(_exc.code))
    except BaseException:  # noqa: BLE001 - reported before the final status
        traceback.print_exc()
        _code = 3
    _flush_failed = False
    try:
        sys.stdout.flush()
    except BaseException:  # noqa: BLE001 - a failed data write is unknown
        traceback.print_exc()
        _flush_failed = True
        if _code == 0:
            _code = 3
    print(f"FLOW_WAVE_COMPLETION_EXIT={_code}", file=sys.stderr)
    if _flush_failed:
        try:
            sys.stderr.flush()
        except BaseException:  # noqa: BLE001 - no remaining reporting channel
            pass
        os._exit(_code)
    raise SystemExit(_code)
