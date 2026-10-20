"""A software WebAuthn authenticator for tests and the e2e script: produces what a browser would (fresh P-256 key, "none" attestation). Needs `cbor2`."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class SoftAuthenticator:
    def __init__(self, rp_id: str, origin: str) -> None:
        self.rp_id = rp_id
        self.origin = origin
        self._key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.counter = 0

    def _rp_id_hash(self) -> bytes:
        return hashlib.sha256(self.rp_id.encode()).digest()

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False}).encode()

    def register(self, options: dict[str, Any]) -> dict[str, Any]:
        """Answer `navigator.credentials.create` for the given creation options."""
        import cbor2

        nums = self._key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})
        auth_data = (
            self._rp_id_hash() + bytes([0x45]) + struct.pack(">I", 0) + bytes(16)
            + struct.pack(">H", len(self.credential_id)) + self.credential_id + cose
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = b64url(self.credential_id)
        return {
            "id": cid, "rawId": cid, "type": "public-key", "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(self._client_data("webauthn.create", options["challenge"])),
                "attestationObject": b64url(attestation),
                "transports": ["internal"],
            },
        }

    def assert_(self, options: dict[str, Any], counter: int | None = None) -> dict[str, Any]:
        """Answer `navigator.credentials.get`; `counter` overrides the signature counter (to test clone detection)."""
        self.counter = counter if counter is not None else self.counter + 1
        auth_data = self._rp_id_hash() + bytes([0x05]) + struct.pack(">I", self.counter)
        client_data = self._client_data("webauthn.get", options["challenge"])
        signed = auth_data + hashlib.sha256(client_data).digest()
        signature = self._key.sign(signed, ec.ECDSA(hashes.SHA256()))
        cid = b64url(self.credential_id)
        return {
            "id": cid, "rawId": cid, "type": "public-key", "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64url(client_data), "authenticatorData": b64url(auth_data), "signature": b64url(signature),
            },
        }
