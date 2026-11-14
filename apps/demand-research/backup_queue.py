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
from contextlib import contextmanager

from demand_archive import CloudArchive, canonical_json, sha256
from target_account_archive import profile_input

_REQUEST=re.compile(r"account-request-([0-9]{10})\.json\Z")
_ACCOUNT=re.compile(r"account-request-([0-9]{10})-accepted\.json\Z")
_MAX_OPEN=64


def enabled():
    return os.getenv("DEMAND_ARCHIVE_QUEUE_MODE","")=="1"


def sqlite_enabled():
    # The free Render disk is ephemeral; lost requests must not be called
    # accepted or verified after a restart.
    return enabled() and os.getenv("DEMAND_ARCHIVE_QUEUE_STORE","")=="sqlite"


@contextmanager
def _db():
    path=Path(os.getenv("DEMAND_ARCHIVE_QUEUE_SQLITE","/tmp/intersection-account-queue.sqlite3"))
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(path),timeout=5)
    conn.row_factory=sqlite3.Row
    try:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS account_requests (
               job_id INTEGER PRIMARY KEY,
               platform TEXT NOT NULL,
               account TEXT NOT NULL,
               created_at INTEGER NOT NULL,
               workflow_run_id INTEGER,
               accepted_at INTEGER,
               created_order INTEGER
            )''')
            # Additive, backward-compatible migration for existing free-tier
            # queue databases; never modify old request identities.
            columns={str(row["name"]) for row in conn.execute(
                "PRAGMA table_info(account_requests)")}
            if "created_order" not in columns:
                conn.execute("ALTER TABLE account_requests ADD COLUMN created_order INTEGER")
            yield conn
    finally:
        conn.close()


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
            open_count=conn.execute("SELECT count(*) FROM account_requests WHERE workflow_run_id IS NULL").fetchone()[0]
            if open_count>=_MAX_OPEN:
                raise RuntimeError("Temporary account queue is full")
            for _ in range(10):
                job_id=1000000000+secrets.randbelow(9000000000)
                try:
                    conn.execute("INSERT INTO account_requests (job_id,platform,account,created_at,created_order) VALUES (?,?,?,?,?)",
                                 (job_id,platform,account,int(time.time()),time.time_ns()))
                    return job_id
                except sqlite3.IntegrityError:
                    continue
            raise RuntimeError("Unable to allocate private account request")
    root=root or CloudArchive()
    job_id=1000000000+secrets.randbelow(9000000000)
    payload={"schema":1,"job_id":job_id,"platform":platform,
             "account":account,"created_at":int(time.time()),
             "created_order":time.time_ns()}
    _save_verified(root,_request_key(job_id),payload)
    return job_id


def pending(root=None,limit=1):
    if not enabled():
        raise RuntimeError("Durable queue disabled")
    if sqlite_enabled():
        with _db() as conn:
            rows=conn.execute('''SELECT * FROM account_requests
                WHERE workflow_run_id IS NULL
                ORDER BY created_at ASC, COALESCE(created_order,job_id) ASC, job_id ASC LIMIT ?''',
                (min(max(limit,1),_MAX_OPEN),)).fetchall()
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


def overview(root=None):
    """Count requests, not completed archives, without exposing account IDs."""
    if not enabled():
        return {"known":False,"mode":"disabled","queued":None,
                "dispatched":None,"total_requests":None}
    if sqlite_enabled():
        with _db() as conn:
            row=conn.execute("""SELECT count(*) AS total,
                sum(CASE WHEN workflow_run_id IS NULL THEN 1 ELSE 0 END) AS queued,
                sum(CASE WHEN workflow_run_id IS NOT NULL THEN 1 ELSE 0 END) AS dispatched
                FROM account_requests""").fetchone()
        return {"known":True,"mode":"volatile_sqlite",
                "queued":int(row["queued"] or 0),
                "dispatched":int(row["dispatched"] or 0),
                "total_requests":int(row["total"] or 0)}
    root=root or CloudArchive()
    names=root.names("")
    request_ids={int(m.group(1)) for name in names
                 if (m:=_REQUEST.fullmatch(name))}
    dispatched_ids={int(m.group(1)) for name in names
                    if (m:=_ACCOUNT.fullmatch(name))}
    return {"known":True,"mode":"immutable_cloud",
            "queued":len(request_ids-dispatched_ids),
            "dispatched":len(request_ids&dispatched_ids),
            "total_requests":len(request_ids)}


def accepted_runs(root=None,limit=64):
    """Return only workflow run IDs for bounded trusted GitHub retry checks.

    The GitHub runner already has a scoped short-lived actions token. Never
    expose account names or raw queue records via this helper's API.
    """
    if not enabled():
        raise RuntimeError("Durable queue disabled")
    maximum=min(max(int(limit),1),64)
    if sqlite_enabled():
        with _db() as conn:
            rows=conn.execute("""SELECT workflow_run_id FROM account_requests
                 WHERE workflow_run_id IS NOT NULL AND accepted_at>=?
                 ORDER BY accepted_at ASC,job_id ASC LIMIT ?""",
                 (int(time.time())-30*86400,maximum)).fetchall()
        return [int(row["workflow_run_id"]) for row in rows]
    root=root or CloudArchive()
    names=root.names("")
    candidates=[]
    for name in names:
        matched=_ACCOUNT.fullmatch(name)
        if matched:
            candidates.append(int(matched.group(1)))
    # Each immutable acknowledgement must be independently verified, never
    # promoted to a successful archive merely because the object exists.
    if len(candidates)>2000:
        raise RuntimeError("Too many accepted backup records to scan safely")
    accepted=[]
    for job_id in candidates[-maximum:]:
        row=read_acceptance(root,job_id)
        if row:
            accepted.append((int(row.get("accepted_at") or 0),
                             row["workflow_run_id"]))
    return [run_id for _,run_id in sorted(accepted)]


def queue_rows(root=None, limit=20, offset=0):
    """Oldest-first snapshot of signed backup request records for owner UI.

    This is a read-only view. It does NOT equate a dispatch acknowledgment
    with successful media preservation or expose tokens/cookies. SQLite's
    ephemeral nature is reported via mode, never concealed from the user.
    """
    if not enabled():
        raise RuntimeError("No trackable durable account request queue configured")
    if type(limit) is not int or not 1<=limit<=40:
        raise ValueError("invalid queue page size")
    if type(offset) is not int or not 0<=offset<=2000:
        raise ValueError("invalid queue offset")
    if sqlite_enabled():
        with _db() as conn:
            total=int(conn.execute("SELECT count(*) FROM account_requests").fetchone()[0])
            rows=conn.execute("""SELECT * FROM account_requests
                 ORDER BY created_at ASC, COALESCE(created_order,job_id) ASC, job_id ASC LIMIT ? OFFSET ?""",
                 (limit,offset)).fetchall()
        items=[]
        for row in rows:
            item=_sqlite_record(row)
            item.update({"workflow_run_id":int(row["workflow_run_id"])
                           if row["workflow_run_id"] is not None else None,
                         "accepted_at":int(row["accepted_at"])
                           if row["accepted_at"] is not None else None})
            items.append(item)
        return {"items":items,"total":total,"mode":"volatile_sqlite",
                "offset":offset,"limit":limit,"truncated":False}

    root=root or CloudArchive()
    candidates=[]
    for name in root.names(""):
        match=_REQUEST.fullmatch(name)
        if match:
            candidates.append(int(match.group(1)))
    if len(candidates)>2000:
        raise RuntimeError("Too many immutable account requests to enumerate safely")
    # Remote account queue reads can be slow; never block the owner UI
    # indefinitely on thousands of private-file downloads. If capped,
    # report that the complete chronology is NOT available.
    truncated=len(candidates)>120
    if truncated:
        candidates=sorted(candidates)[:120]
    items=[]
    for job_id in candidates:
        record=read_request(root,job_id)
        if record is None:
            continue
        ack=read_acceptance(root,job_id)
        items.append({"schema":1,"job_id":job_id,
                      "platform":record["platform"],"account":record["account"],
                      "created_at":record["created_at"],
                      "created_order":record.get("created_order",job_id),
                      "workflow_run_id":ack["workflow_run_id"] if ack else None,
                      "accepted_at":ack["accepted_at"] if ack else None})
    items.sort(key=lambda row:(row["created_at"],row["created_order"],row["job_id"]))
    return {"items":items[offset:offset+limit],
            "total":len(items) if not truncated else None,
            "mode":"immutable_cloud","offset":offset,"limit":limit,
            "truncated":truncated}
