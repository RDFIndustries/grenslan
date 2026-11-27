"""Access-token validation for the MCP-compatible authorization profile (TC-048)."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import pytest

from grenslan.server.oauth import AccessTokenValidator, InvalidAccessToken, TokenPolicy, TrustedIssuer

from jwt_fixtures import ISSUER, RESOURCE, SigningKey, claims, ec_key, rsa_key

SCOPES = {"grenslan.search": frozenset({"web_search", "image_search"}), "grenslan.read": frozenset({"document_read"})}


@pytest.fixture(scope="module")
def key() -> SigningKey:
    return rsa_key()


@pytest.fixture(scope="module")
def other_key() -> SigningKey:
    return rsa_key("rsa-2")


def issuer(*keys: SigningKey, **overrides: Any) -> TrustedIssuer:
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "application_id": "qor",
        "keys": tuple(k.public_jwk() for k in keys),
        "scope_permissions": SCOPES,
        "user_claim": "sub",
    }
    values.update(overrides)
    return TrustedIssuer(**values)


def validator(*issuers: TrustedIssuer, max_lifetime: int = 3600) -> AccessTokenValidator:
    policy = TokenPolicy(resource=RESOURCE, leeway_seconds=30, max_lifetime_seconds=max_lifetime)
    return AccessTokenValidator(policy, issuers)


def b64(data: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_valid_token_yields_scoped_principal(key: SigningKey) -> None:
    principal = validator(issuer(key)).validate(key.sign(claims(scope="grenslan.search other")))
    assert principal.application_id == "qor"
    assert principal.permissions == frozenset({"web_search", "image_search"})
    assert principal.user_id == "user-1"
    assert principal.delegation is False
    assert principal.agent_id is None
    assert principal.instance_id is None
    assert principal.issuer == ISSUER


def test_ec_keys_are_accepted() -> None:
    key = ec_key()
    assert validator(issuer(key)).validate(key.sign(claims())).application_id == "qor"


def test_no_scope_yields_no_permissions(key: SigningKey) -> None:
    principal = validator(issuer(key)).validate(key.sign(claims(scope=None)))
    assert principal.permissions == frozenset()


def test_user_claim_is_optional(key: SigningKey) -> None:
    principal = validator(issuer(key, user_claim=None)).validate(key.sign(claims()))
    assert principal.user_id is None


def test_expiry_is_reported(key: SigningKey) -> None:
    exp = int(time.time()) + 120
    principal = validator(issuer(key)).validate(key.sign(claims(exp=exp)))
    assert principal.expires_at == exp


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"aud": "https://other.example/mcp"}, id="wrong-audience"),
        pytest.param({"aud": None}, id="no-audience"),
        pytest.param({"iss": "https://evil.example"}, id="unknown-issuer"),
        pytest.param({"iss": None}, id="no-issuer"),
        pytest.param({"exp": int(time.time()) - 120}, id="expired"),
        pytest.param({"exp": None}, id="no-expiry"),
        pytest.param({"iat": None}, id="no-issued-at"),
        pytest.param({"nbf": int(time.time()) + 600}, id="not-yet-valid"),
        pytest.param({"exp": int(time.time()) + 7200, "iat": int(time.time())}, id="lifetime-too-long"),
        pytest.param({"sub": "bad user!"}, id="invalid-user-identity"),
        pytest.param({"sub": None}, id="missing-user-claim"),
        pytest.param({"scope": ["grenslan.search"]}, id="non-string-scope"),
    ],
)
def test_invalid_claims_are_rejected(key: SigningKey, overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(key.sign(claims(**overrides)))


def test_wrong_signing_key_is_rejected(key: SigningKey, other_key: SigningKey) -> None:
    forged = other_key.sign(claims(), kid=key.kid)
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(forged)


def test_unknown_key_id_is_rejected(key: SigningKey, other_key: SigningKey) -> None:
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(other_key.sign(claims()))


def test_key_id_selects_among_several_keys(key: SigningKey, other_key: SigningKey) -> None:
    assert validator(issuer(key, other_key)).validate(other_key.sign(claims())).application_id == "qor"


@pytest.mark.parametrize(
    "header",
    [
        pytest.param({"jku": "https://evil.example/jwks"}, id="jku"),
        pytest.param({"x5u": "https://evil.example/cert"}, id="x5u"),
        pytest.param({"jwk": {"kty": "RSA"}}, id="jwk"),
        pytest.param({"x5c": ["MIIB"]}, id="x5c"),
        pytest.param({"crit": ["exp"]}, id="crit"),
        pytest.param({"typ": "id_token+jwt"}, id="wrong-type"),
    ],
)
def test_forbidden_headers_are_rejected(key: SigningKey, header: dict[str, Any]) -> None:
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(key.sign(claims(), **header))


def test_unsigned_token_is_rejected(key: SigningKey) -> None:
    token = f"{b64({'alg': 'none', 'kid': key.kid})}.{b64(claims())}."
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(token)


def test_hmac_with_public_key_is_rejected(key: SigningKey) -> None:
    import hashlib
    import hmac

    jwk = key.public_jwk()
    signing_input = f"{b64({'alg': 'HS256', 'kid': key.kid})}.{b64(claims())}"
    signature = hmac.new(json.dumps(jwk).encode(), signing_input.encode(), hashlib.sha256).digest()
    token = f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(token)


def test_algorithm_must_match_the_key() -> None:
    rsa_signer, ec_signer = rsa_key("same"), ec_key("same")
    with pytest.raises(InvalidAccessToken):
        validator(issuer(rsa_signer)).validate(ec_signer.sign(claims()))


@pytest.mark.parametrize("token", ["", "abc", "a.b", "a.b.c.d", "....", "a.b.c"])
def test_malformed_tokens_are_rejected(key: SigningKey, token: str) -> None:
    with pytest.raises(InvalidAccessToken):
        validator(issuer(key)).validate(token)


def test_failure_message_does_not_reveal_the_reason(key: SigningKey) -> None:
    messages = set()
    for overrides in ({"aud": "https://other.example"}, {"exp": int(time.time()) - 120}, {"iss": "https://x.example"}):
        with pytest.raises(InvalidAccessToken) as excinfo:
            validator(issuer(key)).validate(key.sign(claims(**overrides)))
        messages.add(str(excinfo.value))
    assert messages == {"invalid access token"}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param({"d": "AAAA"}, "private", id="private-key-material"),
        pytest.param({"kty": "oct", "k": "AAAA"}, "private", id="symmetric-key"),
        pytest.param({"alg": "HS256"}, "algorithm", id="hmac-algorithm"),
        pytest.param({"alg": "RS512"}, "algorithm", id="unsupported-algorithm"),
        pytest.param({"use": "enc"}, "use", id="encryption-key"),
    ],
)
def test_unsafe_keys_are_refused_at_configuration(key: SigningKey, overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        issuer(keys=(key.public_jwk(**overrides),))


def test_short_rsa_keys_are_refused() -> None:
    with pytest.raises(ValueError, match="2048"):
        issuer(rsa_key(bits=1024))


def test_several_keys_need_distinct_key_ids(key: SigningKey) -> None:
    with pytest.raises(ValueError, match="kid"):
        issuer(keys=(key.public_jwk(), key.public_jwk()))
    with pytest.raises(ValueError, match="kid"):
        issuer(keys=(key.public_jwk(kid=None), rsa_key("x").public_jwk()))


@pytest.mark.parametrize("value", ["http://idp.example", "https://idp.example#frag", "idp.example"])
def test_issuer_must_be_an_https_url(key: SigningKey, value: str) -> None:
    with pytest.raises(ValueError, match="issuer"):
        issuer(key, issuer=value)


@pytest.mark.parametrize("resource", ["http://localhost/mcp", "https://localhost/mcp?x=1", "https://localhost/mcp#f"])
def test_resource_must_be_an_https_url_without_query_or_fragment(resource: str) -> None:
    with pytest.raises(ValueError, match="resource"):
        TokenPolicy(resource=resource, leeway_seconds=0, max_lifetime_seconds=60)


def test_duplicate_issuers_are_refused(key: SigningKey) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validator(issuer(key), issuer(key))


def test_protected_resource_metadata(key: SigningKey) -> None:
    tokens = validator(issuer(key))
    assert tokens.metadata_path == "/.well-known/oauth-protected-resource/mcp"
    assert tokens.metadata_url == "https://localhost/.well-known/oauth-protected-resource/mcp"
    assert tokens.metadata() == {
        "resource": RESOURCE,
        "authorization_servers": [ISSUER],
        "scopes_supported": ["grenslan.read", "grenslan.search"],
        "bearer_methods_supported": ["header"],
    }


def test_replacing_issuers_revokes_tokens_from_removed_keys(key: SigningKey, other_key: SigningKey) -> None:
    tokens = validator(issuer(key, other_key))
    principal = tokens.validate(key.sign(claims()))
    survivor = tokens.validate(other_key.sign(claims()))
    revoked, kept = [], []
    tokens.watch(principal, lambda: revoked.append(True))
    tokens.watch(survivor, lambda: kept.append(True))
    tokens.replace([issuer(other_key)])
    assert revoked == [True]
    assert kept == []
    with pytest.raises(InvalidAccessToken):
        tokens.validate(key.sign(claims()))


def test_changing_an_issuer_revokes_its_tokens(key: SigningKey) -> None:
    tokens = validator(issuer(key))
    principal = tokens.validate(key.sign(claims()))
    revoked: list[bool] = []
    tokens.watch(principal, lambda: revoked.append(True))
    tokens.replace([issuer(key, scope_permissions={})])
    assert revoked == [True]


def test_watching_a_stale_principal_calls_back_immediately(key: SigningKey) -> None:
    tokens = validator(issuer(key))
    principal = tokens.validate(key.sign(claims()))
    tokens.replace([])
    revoked: list[bool] = []
    tokens.watch(principal, lambda: revoked.append(True))
    assert revoked == [True]


def test_issuer_settings_are_copied_at_configuration(key: SigningKey) -> None:
    scopes = {"grenslan.search": frozenset({"web_search"})}
    jwk = key.public_jwk()
    tokens = validator(issuer(keys=(jwk,), scope_permissions=scopes))
    scopes["grenslan.search"] = frozenset({"web_search", "document_read"})
    jwk["kid"] = "changed"
    principal = tokens.validate(key.sign(claims()))
    assert principal.permissions == frozenset({"web_search"})
