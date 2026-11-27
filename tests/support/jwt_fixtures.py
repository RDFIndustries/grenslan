"""Throwaway signing keys and access tokens for OAuth tests. Nothing here is a real credential."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

ISSUER = "https://idp.example"
RESOURCE = "https://localhost/mcp"


@dataclass(frozen=True)
class SigningKey:
    private_key: Any
    algorithm: str
    kid: str

    def public_jwk(self, **overrides: Any) -> dict[str, Any]:
        converter = RSAAlgorithm if self.algorithm == "RS256" else ECAlgorithm
        jwk: dict[str, Any] = dict(converter.to_jwk(self.private_key.public_key(), as_dict=True))
        jwk.update({"kid": self.kid, "alg": self.algorithm, "use": "sig"})
        jwk.update(overrides)
        return {name: value for name, value in jwk.items() if value is not None}

    def sign(self, claims: dict[str, Any], **headers: Any) -> str:
        header = {"kid": self.kid, "typ": "at+jwt", **headers}
        header = {name: value for name, value in header.items() if value is not None}
        return jwt.encode(claims, self.private_key, algorithm=self.algorithm, headers=header)


def rsa_key(kid: str = "rsa-1", bits: int = 2048) -> SigningKey:
    return SigningKey(rsa.generate_private_key(public_exponent=65537, key_size=bits), "RS256", kid)


def ec_key(kid: str = "ec-1") -> SigningKey:
    return SigningKey(ec.generate_private_key(ec.SECP256R1()), "ES256", kid)


def claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    base: dict[str, Any] = {
        "iss": ISSUER,
        "aud": RESOURCE,
        "sub": "user-1",
        "iat": now,
        "exp": now + 300,
        "scope": "grenslan.search",
    }
    base.update(overrides)
    return {name: value for name, value in base.items() if value is not None}
