"""Ephemeral-free TeraBox credential delivery for the dedicated Render server.

GitHub Actions already possesses the NDUS from GitHub Secrets. It encrypts
the secret to a Render-only X25519 private key, then commits ONLY ciphertext
to a dedicated public branch. Render decrypts on cold start. The private key
must exist only in Render's persisted, secret environment setting.

No plaintext NDUS, session link or unsealed payload is ever committed.
"""
from __future__ import annotations
import base64
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import quote
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidTag

SCHEMA=1
AAD=b"intersection:render:terabox:ndus:v1"
INFO=b"intersection:sealed:ndus:hkdf:v1"
PUBLIC_KEY="UC4K-4fgi59pg8sL3QnXe-VP_ap3XarbcbFn-bDd1x8"
REPO="koith/browser-app-lab"
BRANCH="intersection-credential-sealed"
PATH="apps/demand-research/.sealed-credential.json"
RAW="https://raw.githubusercontent.com/"+REPO+"/"+BRANCH+"/"+PATH


def _decode(text,limit=12000):
    if not isinstance(text,str) or not 10<=len(text)<=limit:
        raise ValueError("Invalid sealed credential encoding")
    try:
        return base64.urlsafe_b64decode(text+"="*((-len(text))%4))
    except (ValueError,TypeError):
        raise ValueError("Invalid sealed credential encoding") from None


def _encode(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _derive(shared,salt):
    return HKDF(algorithm=hashes.SHA256(),length=32,
                salt=salt,info=INFO).derive(shared)


def seal(secret):
    if not isinstance(secret,str) or not 16<=len(secret)<=4096:
        raise ValueError("Invalid source credential")
    if any(ord(ch)<32 for ch in secret):
        raise ValueError("Invalid source credential")
    receiver=x25519.X25519PublicKey.from_public_bytes(_decode(PUBLIC_KEY))
    ephemeral=x25519.X25519PrivateKey.generate()
    salt=os.urandom(16)
    nonce=os.urandom(12)
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    pub=ephemeral.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    ciphertext=AESGCM(_derive(ephemeral.exchange(receiver),salt)).encrypt(
        nonce,secret.encode("utf-8"),AAD)
    return {"schema_version":SCHEMA,"ephemeral":_encode(pub),
            "salt":_encode(salt),"nonce":_encode(nonce),
            "ciphertext":_encode(ciphertext)}


def unseal(envelope,private_key):
    if (not isinstance(envelope,dict) or set(envelope)!={
            "schema_version","ephemeral","salt","nonce","ciphertext"} or
            envelope["schema_version"]!=SCHEMA):
        raise ValueError("Unsupported credential envelope")
    keyraw=_decode(private_key)
    if len(keyraw)!=32:
        raise ValueError("Invalid server key")
    peer=_decode(envelope["ephemeral"])
    salt=_decode(envelope["salt"])
    nonce=_decode(envelope["nonce"])
    body=_decode(envelope["ciphertext"])
    if len(peer)!=32 or len(salt)!=16 or len(nonce)!=12 or len(body)>4200:
        raise ValueError("Malformed credential envelope")
    local=x25519.X25519PrivateKey.from_private_bytes(keyraw)
    counterpart=x25519.X25519PublicKey.from_public_bytes(peer)
    try:
        plaintext=AESGCM(_derive(local.exchange(counterpart),salt)).decrypt(nonce,body,AAD)
        value=plaintext.decode("utf-8")
    except (InvalidTag,UnicodeDecodeError):
        raise ValueError("Credential authenticity check failed") from None
    if not 16<=len(value)<=4096 or any(ord(c)<32 for c in value):
        raise ValueError("Invalid recovered credential")
    return value


def restore_from_github(private_key):
    request=Request(RAW+"?cache-bust="+str(int(__import__("time").time()//60)),
       headers={"Accept":"application/json",
                "User-Agent":"intersection-render-sealed-restore"})
    with urlopen(request,timeout=12) as response:
        if response.status!=200:
            raise RuntimeError("Sealed credential archive unavailable")
        raw=response.read(12000)
    data=json.loads(raw)
    return unseal(data,private_key)


def publish_encrypted():
    source=os.environ.get("TERABOX_PRIVATE_NDUS","")
    token=os.environ.get("GITHUB_TOKEN","")
    if not token or not source:
        raise RuntimeError("GitHub Actions credentials are missing")
    sealed=seal(source)
    obj=json.dumps(sealed,sort_keys=True,separators=(",",":")).encode("utf-8")
    endpoint="https://api.github.com/repos/"+REPO+"/contents/"+PATH
    def github_request(method,url,payload=None):
        body=json.dumps(payload).encode("utf-8") if payload is not None else None
        request=Request(url,method=method,data=body,
          headers={"Accept":"application/vnd.github+json",
                   "X-GitHub-Api-Version":"2022-11-28",
                   "Authorization":"Bearer "+token,
                   "User-Agent":"intersection-sealed-credential-writer",
                   **({"Content-Type":"application/json"} if body is not None else {})})
        with urlopen(request,timeout=30) as response:
            return json.load(response)
    previous=github_request("GET",endpoint+"?ref="+quote(BRANCH,safe=""))
    if not isinstance(previous,dict) or not isinstance(previous.get("sha"),str):
        raise RuntimeError("Sealed credential branch not initialized")
    response=github_request("PUT",endpoint,{
       "message":"chore(intersection): refresh sealed Render cloud credential",
       "branch":BRANCH,"sha":previous["sha"],
       "content":base64.b64encode(obj).decode("ascii")})
    if response.get("content",{}).get("path")!=PATH:
        raise RuntimeError("Encrypted archive update not confirmed")
    print("INTERSECTION_ENCRYPTED_CREDENTIAL_PERSISTED")


if __name__=="__main__":
    publish_encrypted()
