"""Restart-safe encrypted state, bound to this server's existing private key.

Plain account cookies never leave the gateway. Ciphertext belongs only in the
same Render service's private environment, never source, artifacts or logs.
"""
import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def cipher(token):
    if not isinstance(token,str) or len(token)<8:raise ValueError('Owner server key unavailable')
    key=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,
             info=b'owner-gallery-terabox-restart-state-v1').derive(token.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def valid(cookie):
    if not isinstance(cookie,str) or not 8<=len(cookie)<=16000 or any(ord(c)<32 or ord(c)==127 for c in cookie):
        raise ValueError('Invalid owner connection state')
    return cookie


def seal(cookie,token):
    raw=json.dumps({'schema_version':1,'cookie':valid(cookie)},separators=(',',':')).encode()
    return 'v1:'+cipher(token).encrypt(raw).decode()


def restore(value,token):
    try:
        if not isinstance(value,str) or not value.startswith('v1:'):raise ValueError()
        data=json.loads(cipher(token).decrypt(value[3:].encode()))
        if data['schema_version']!=1:raise ValueError()
        return valid(data['cookie'])
    except Exception:raise ValueError('Invalid sealed owner connection state') from None
