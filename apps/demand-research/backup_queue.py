"""Durable selected-account backup queue stored as immutable TeraBox root objects.

A private browser never receives the GitHub token. A trusted GitHub Actions
OIDC bridge polls this queue and dispatches with its own *job-scoped* token.
A queue acknowledgment is not a completed or verified backup.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import sqlite3
from pathlib import Path

from demand_archive import CloudArchive, canonical_json, sha256
from target_account_archive import profile_input

_REQUEST=re.compile(r"account-request-([0-9]{10})\.json\Z")
_ACCOUNT=re.compile(r"account-request-([0-9]{10})-accepted\.json\Z")
_MAX_OPEN=12


def enabled():
    return os.getenv("DEMAND_ARCHIVE_QUEUE_MODE","")=="1"


def sqlite_enabled():
    # The free Render disk is ephemeral; lost requests must not be called
    # accepted or verified after a restart.
    return enabled() and os.getenv("DEMAND_ARCHIVE_QUEUE_STORE","")=="sqlite"


def _db():
    path=Path(os.getenv("DEMAND_ARCHIVE_QUEUE_SQLITE","/tmp/intersection-account-queue.sqlite3"))
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(path),timeout=5)
    conn.row_factory=sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS account_requests (
       job_id INTEGER PRIMARY KEY,
       platform TEXT NOT NULL,
       account TEXT NOT NULL,
       created_at INTEGER NOT NULL,
       workflow_run_id INTEGER,
       accepted_at INTEGER
    )''')
    return conn


def _sqlite_record(row):
    if row is None:
        return None
    return {"schema":1,"job_id":int(row["job_id"]),"platform":row["platform"],
            "account":row["account"],"created_at":int(row["created_at"])}


def _sqlite_accept(row):
    if row is None or row["workflow_run_id"] is None:
        return None
    return {"schema":1,"job_id":int(row["job_id"]),
            "workflow_run_id":int(row["workflow_run_id"]),
            "accepted_at":int(row["accepted_at"])}





def _num(job_id):
    if type(job_id) is not int or not 1000000000 <= job_id <= 9999999999:
        raise ValueError("invalid backup request id")
    return job_id


def _request_key(job_id):
    return "account-request-"+str(_num(job_id))+".json"


def _accepted_key(job_id):
    return "account-request-"+str(_num(job_id))+"-accepted.json"


def _read_object(root,key):
    raw=root.read(key,cap=4096,optional=True)
    if raw is None:
        return None
    if len(raw)>4096:
        raise RuntimeError("Oversized backup queue entry")
    try:
        result=json.loads(raw)
    except (ValueError,TypeError):
        raise RuntimeError("Damaged immutable backup queue entry") from None
    if type(result) is not dict:
        raise RuntimeError("Invalid immutable backup queue entry")
    return result


def read_request(root,job_id):
    if sqlite_enabled():
        with _db() as conn:
            row=conn.execute("SELECT * FROM account_requests WHERE job_id=?",(_num(job_id),)).fetchone()
        return _sqlite_record(row)
    row=_read_object(root,_request_key(job_id))
    if row is None:
        return None
    if (row.get("schema")!=1 or row.get("job_id")!=job_id
            or type(row.get("platform")) is not str
            or type(row.get("account")) is not str
            or type(row.get("created_at")) is not int):
        raise RuntimeError("Invalid backup request record")
    try:
        profile_input(row["platform"],row["account"])
    except (ValueError,TypeError,KeyError):
        raise RuntimeError("Untrusted account backup record") from None
    return row


def read_acceptance(root,job_id):
    if sqlite_enabled():
        with _db() as conn:
            row=conn.execute("SELECT * FROM account_requests WHERE job_id=?",(_num(job_id),)).fetchone()
        return _sqlite_accept(row)
    row=_read_object(root,_accepted_key(job_id))
    if row is None:
        return None
    if (row.get("schema")!=1 or row.get("job_id")!=job_id
            or type(row.get("workflow_run_id")) is not int
            or row["workflow_run_id"]<=0):
        raise RuntimeError("Invalid backup acceptance record")
    return row


def _save_verified(root,key,payload):
    data=canonical_json(payload)
    if isinstance(root, CloudArchive):
        root.trace_queue = True
    started = time.monotonic()
    stage = "write_immutable"
    outcome = "error"
    try:
        root.write_immutable(key,data)
        print("BACKUP_QUEUE_STAGE stage=write_immutable outcome=ok elapsed_ms=" +
              str(round((time.monotonic()-started)*1000)), flush=True)
        stage = "read_verified"
        started = time.monotonic()
        verified=root.read_verified(key,sha256(data),cap=len(data)+1)
        outcome = "ok" if verified == data else "sha_unverified"
    finally:
        print("BACKUP_QUEUE_STAGE stage=" + stage + " outcome=" + outcome + " elapsed_ms=" +
              str(round((time.monotonic()-started)*1000)), flush=True)
    if verified!=data:
        raise RuntimeError("Backup request did not pass private storage readback")


def create_request(platform,account,root=None):
    if not enabled():
        raise RuntimeError("Durable queue disabled")
    normalized=profile_input(platform,account)
    if platform=="bluesky" and not account.startswith("https://"):
        account=normalized
    if sqlite_enabled():
        with _db() as conn:
            open_count=conn.execute("SELECT count(*) FROM account_requests WHERE workflow_run_id IS NULL AND created_at>?",
                                    (int(time.time())-86400,)).fetchone()[0]
            if open_count>=_MAX_OPEN:
                raise RuntimeError("Temporary account queue is full")
            for _ in range(10):
                job_id=1000000000+secrets.randbelow(9000000000)
                try:
                    conn.execute("INSERT INTO account_requests (job_id,platform,account,created_at) VALUES (?,?,?,?)",
                                 (job_id,platform,account,int(time.time())))
                    return job_id
                except sqlite3.IntegrityError:
                    continue
            raise RuntimeError("Unable to allocate private account request")
    root=root or CloudArchive()
    job_id=1000000000+secrets.randbelow(9000000000)
    payload={"schema":1,"job_id":job_id,"platform":platform,
             "account":account,"created_at":int(time.time())}
    _save_verified(root,_request_key(job_id),payload)
    return job_id


def pending(root=None,limit=1):
    if not enabled():
        raise RuntimeError("Durable queue disabled")
    if sqlite_enabled():
        with _db() as conn:
            rows=conn.execute('''SELECT * FROM account_requests
                WHERE workflow_run_id IS NULL AND created_at>?
                ORDER BY created_at ASC, job_id ASC LIMIT ?''',
                (int(time.time())-86400,min(max(limit,1),_MAX_OPEN))).fetchall()
        return [{"job_id":int(row["job_id"]),"platform":row["platform"],
                 "account":row["account"]} for row in rows]
    root=root or CloudArchive()
    candidates=[]
    for name in root.names(""):
        m=_REQUEST.fullmatch(name)
        if m:
            candidates.append(int(m.group(1)))
    if len(candidates)>2000:
        raise RuntimeError("Too many private backup requests to scan safely")
    selected=[]
    for job_id in sorted(candidates):
        if read_acceptance(root,job_id) is not None:
            continue
        row=read_request(root,job_id)
        if row:
            selected.append({"job_id":job_id,"platform":row["platform"],
                             "account":row["account"]})
        if len(selected)>=min(max(limit,1),_MAX_OPEN):
            break
    return selected


def accept(job_id,workflow_run_id,root=None):
    if not enabled():
        raise RuntimeError("Durable queue disabled")
    _num(job_id)
    if type(workflow_run_id) is not int or workflow_run_id<=0:
        raise ValueError("invalid workflow run")
    if sqlite_enabled():
        with _db() as conn:
            cursor=conn.execute('''UPDATE account_requests SET workflow_run_id=?, accepted_at=?
                WHERE job_id=? AND workflow_run_id IS NULL''',
                (workflow_run_id,int(time.time()),job_id))
            if cursor.rowcount!=1:
                raise ValueError("Unknown or already accepted private account request")
            row=conn.execute("SELECT * FROM account_requests WHERE job_id=?",(job_id,)).fetchone()
        return _sqlite_accept(row)
    root=root or CloudArchive()
    if read_request(root,job_id) is None:
        raise ValueError("Unknown backup request")
    entry={"schema":1,"job_id":job_id,"workflow_run_id":workflow_run_id,
           "accepted_at":int(time.time())}
    _save_verified(root,_accepted_key(job_id),entry)
    return entry


def state(job_id,root=None):
    _num(job_id)
    if sqlite_enabled():
        with _db() as conn:
            row=conn.execute("SELECT * FROM account_requests WHERE job_id=?",(job_id,)).fetchone()
        return {"request":_sqlite_record(row),"accepted":_sqlite_accept(row)} if row else None
    root=root or CloudArchive()
    request=read_request(root,job_id)
    if request is None:
        return None
    receipt=read_acceptance(root,job_id)
    return {"request":request,"accepted":receipt}
