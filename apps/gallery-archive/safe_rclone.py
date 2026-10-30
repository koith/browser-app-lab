"""Run the existing owner-storage client without leaking signed CDN URLs."""
import subprocess
import sys
import tempfile
import os
import re


def diagnostic(raw):
    # Keep actionable storage errors, never credentials or signed media URLs.
    for key,value in os.environ.items():
        if value and len(value)>5 and any(word in key.upper() for word in ('COOKIE','TOKEN','SECRET','PASSWORD')):
            raw=raw.replace(value,'[redacted]')
    raw=re.sub(r'https?://[^\s"<>]+','[remote URL]',raw)
    raw=re.sub(r'(?i)(cookie|authorization|ndus|token)[=:]\s*[^\s]+',r'\1=[redacted]',raw)
    return '\n'.join(line for line in raw.splitlines() if 'error' in line.lower() or 'failed' in line.lower())[-2400:]


def run(args):
    if not args or args[0] not in ('cat','copy','copyto','about'):raise ValueError('Unsupported storage operation')
    # stdout remains the caller's byte stream, including catalog redirections.
    # Never relay raw stderr: rclone embeds signed download URLs in errors.
    with tempfile.TemporaryFile() as errors:
        result=subprocess.run(['rclone',*args],stderr=errors)
        if result.returncode:
            errors.seek(0);raw=errors.read(32000).decode('utf-8','replace');text=raw.lower()
            cause=next((label for needle,label in [('failed to login','storage_session'),('timeout','remote_timeout'),
                ('403','access_denied'),('451','legal_restriction'),('not found','missing_object')] if needle in text),'storage_operation')
            print('OWNER_STORAGE_FAILED',args[0],cause,'exit',result.returncode,file=sys.stderr)
            print(diagnostic(raw),file=sys.stderr)
        return result.returncode


if __name__=='__main__':raise SystemExit(run(sys.argv[1:]))
