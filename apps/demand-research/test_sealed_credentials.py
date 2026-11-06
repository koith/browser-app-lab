"""No real GitHub secret or Render key. Verify end-to-end authenticated encryption."""
import base64
import json
import os
import pytest
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
import sealed_credentials as vault


def urlsafe(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def test_sealed_ndus_is_only_decryptable_with_private_render_key(monkeypatch):
    server=x25519.X25519PrivateKey.generate()
    sk=urlsafe(server.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
    pk=urlsafe(server.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
    monkeypatch.setattr(vault,"PUBLIC_KEY",pk)
    sample="synthetic-public-archive-ndus-credential-"+"x"*35
    sealed=vault.seal(sample)
    wire=json.dumps(sealed)
    assert sample not in wire
    assert vault.unseal(sealed,sk)==sample
    assert vault.unseal(vault.seal(sample),sk)==sample
    wrong=x25519.X25519PrivateKey.generate()
    wrong_key=urlsafe(wrong.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()))
    with pytest.raises(ValueError,match="authenticity"):
        vault.unseal(sealed,wrong_key)
    bad=dict(sealed);bad["ciphertext"]=urlsafe(
        bytes([1^vault._decode(sealed["ciphertext"])[0]])+
        vault._decode(sealed["ciphertext"])[1:])
    with pytest.raises(ValueError,match="authenticity"):
        vault.unseal(bad,sk)
    with pytest.raises(ValueError):
        vault.unseal({"schema_version":0},sk)


def test_sealed_envelope_rejects_unsafe_plaintext():
    with pytest.raises(ValueError):
        vault.seal("short")
    with pytest.raises(ValueError):
        vault.seal("malicious\nnewline-credential-overlong")
