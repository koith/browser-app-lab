"""Run the existing owner-storage client without leaking signed CDN URLs."""
import subprocess
import sys
import tempfile


def run(args):
    if not args or args[0] not in ('cat','copy','copyto'):raise ValueError('Unsupported storage operation')
    # stdout remains the caller's byte stream, including catalog redirections.
    # Never relay raw stderr: rclone embeds signed download URLs in errors.
    with tempfile.TemporaryFile() as errors:
        result=subprocess.run(['rclone',*args],stderr=errors)
        if result.returncode:
            errors.seek(0);text=errors.read(16000).decode('utf-8','replace').lower()
            cause=next((label for needle,label in [('failed to login','storage_session'),('timeout','remote_timeout'),
                ('403','access_denied'),('451','legal_restriction'),('not found','missing_object')] if needle in text),'storage_operation')
            print('OWNER_STORAGE_FAILED',args[0],cause,'exit',result.returncode,file=sys.stderr)
        return result.returncode


if __name__=='__main__':raise SystemExit(run(sys.argv[1:]))
