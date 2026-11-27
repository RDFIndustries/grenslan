"""Application credential authentication and trusted context (TC-003, TC-048)."""

from __future__ import annotations

import dataclasses

import pytest

from grenslan.server.auth import (
    ApplicationCredential,
    AuthenticationFailed,
    ContextRejected,
    CredentialStore,
    establish_context,
    token_digest,
)

TOKEN_A = "a" * 43
TOKEN_B = "b" * 43


def credential(
    token: str = TOKEN_A,
    *,
    credential_id: str = "cred-a",
    application_id: str = "app-a",
    delegation: bool = False,
    user_id: str | None = "service-user",
) -> ApplicationCredential:
    return ApplicationCredential(
        credential_id=credential_id,
        application_id=application_id,
        token_sha256=token_digest(token),
        permissions=frozenset({"web_search", "capabilities_get"}),
        delegation=delegation,
        user_id=user_id,
        agent_id=None,
        instance_id=None,
    )


def header(token: str) -> list[bytes]:
    return [f"Bearer {token}".encode()]


def test_valid_bearer_token_authenticates() -> None:
    store = CredentialStore([credential()])
    assert store.authenticate(header(TOKEN_A)).application_id == "app-a"


def test_scheme_is_case_insensitive() -> None:
    store = CredentialStore([credential()])
    assert store.authenticate([f"bearer {TOKEN_A}".encode()]).credential_id == "cred-a"


@pytest.mark.parametrize(
    "values",
    [
        [],
        [b"Bearer " + TOKEN_B.encode()],
        [b"Basic " + TOKEN_A.encode()],
        [b"Bearer"],
        [b"Bearer  " + TOKEN_A.encode()],
        [b"Bearer " + TOKEN_A.encode() + b" extra"],
        [b"Bearer " + TOKEN_A.encode(), b"Bearer " + TOKEN_A.encode()],
        [b"Bearer \xff\xfe"],
        [b"Bearer " + b"a" * 5000],
    ],
)
def test_invalid_authorization_is_rejected(values: list[bytes]) -> None:
    store = CredentialStore([credential()])
    with pytest.raises(AuthenticationFailed):
        store.authenticate(values)


def test_failure_does_not_reveal_reason_or_token() -> None:
    store = CredentialStore([credential()])
    with pytest.raises(AuthenticationFailed) as excinfo:
        store.authenticate(header(TOKEN_B))
    assert TOKEN_B not in str(excinfo.value)
    assert str(excinfo.value) == "authentication failed"


def test_only_token_digests_are_held() -> None:
    cred = credential()
    assert TOKEN_A not in repr(cred)
    assert TOKEN_A.encode() not in cred.token_sha256


def test_duplicate_credentials_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        CredentialStore([credential(), credential(credential_id="cred-b")])
    with pytest.raises(ValueError, match="duplicate"):
        CredentialStore([credential(), credential(TOKEN_B)])


def test_replacing_credentials_revokes_removed_tokens() -> None:
    store = CredentialStore([credential()])
    store.replace([credential(TOKEN_B, credential_id="cred-b")])
    with pytest.raises(AuthenticationFailed):
        store.authenticate(header(TOKEN_A))
    assert store.authenticate(header(TOKEN_B)).credential_id == "cred-b"


def test_is_current_reflects_replacement() -> None:
    store = CredentialStore([credential()])
    current = store.authenticate(header(TOKEN_A))
    assert store.is_current(current)
    store.replace([credential(TOKEN_B, credential_id="cred-b")])
    assert not store.is_current(current)


def test_changed_permissions_make_old_credential_record_stale() -> None:
    store = CredentialStore([credential()])
    current = store.authenticate(header(TOKEN_A))
    narrowed = dataclasses.replace(current, permissions=frozenset({"capabilities_get"}))
    store.replace([narrowed])
    assert not store.is_current(current)


def test_context_without_delegation_uses_operator_defined_identity() -> None:
    context = establish_context(credential(), {})
    assert (context.application_id, context.user_id, context.agent_id, context.instance_id) == (
        "app-a",
        "service-user",
        None,
        None,
    )
    assert context.permissions == frozenset({"web_search", "capabilities_get"})


def test_delegation_headers_require_delegating_credential() -> None:
    with pytest.raises(ContextRejected) as excinfo:
        establish_context(credential(), {"grenslan-user-id": [b"alice"]})
    assert excinfo.value.status == 403


def test_delegated_identities_are_applied() -> None:
    context = establish_context(
        credential(delegation=True),
        {"grenslan-user-id": [b"alice"], "grenslan-agent-id": [b"researcher"], "grenslan-instance-id": [b"run-7"]},
    )
    assert (context.application_id, context.user_id, context.agent_id, context.instance_id) == (
        "app-a",
        "alice",
        "researcher",
        "run-7",
    )


def test_delegating_credential_without_headers_uses_defaults() -> None:
    context = establish_context(credential(delegation=True), {})
    assert context.user_id == "service-user"


@pytest.mark.parametrize(
    "values",
    [
        [b"alice", b"bob"],
        [b""],
        [b"alice bob"],
        [b"alice,bob"],
        [b"x" * 129],
        [b"\xc3\xa9"],
        [b"../etc"],
    ],
)
def test_invalid_delegation_values_are_rejected(values: list[bytes]) -> None:
    with pytest.raises(ContextRejected) as excinfo:
        establish_context(credential(delegation=True), {"grenslan-user-id": values})
    assert excinfo.value.status == 400


def test_namespace_cannot_be_claimed_by_header() -> None:
    with pytest.raises(ContextRejected) as excinfo:
        establish_context(credential(delegation=True), {"grenslan-application-id": [b"app-b"]})
    assert excinfo.value.status == 400


def test_watch_notifies_when_credential_is_revoked() -> None:
    store = CredentialStore([credential()])
    current = store.authenticate(header(TOKEN_A))
    calls: list[str] = []
    store.watch(current, lambda: calls.append("revoked"))
    store.replace([credential()])
    assert calls == []
    store.replace([])
    assert calls == ["revoked"]


def test_watch_notifies_when_credential_record_changes() -> None:
    store = CredentialStore([credential()])
    current = store.authenticate(header(TOKEN_A))
    calls: list[str] = []
    store.watch(current, lambda: calls.append("changed"))
    store.replace([dataclasses.replace(current, permissions=frozenset())])
    assert calls == ["changed"]


def test_unwatch_stops_notification() -> None:
    store = CredentialStore([credential()])
    current = store.authenticate(header(TOKEN_A))
    calls: list[str] = []
    unwatch = store.watch(current, lambda: calls.append("revoked"))
    unwatch()
    store.replace([])
    assert calls == []


def test_watching_a_stale_record_notifies_immediately() -> None:
    store = CredentialStore([credential()])
    current = store.authenticate(header(TOKEN_A))
    store.replace([])
    calls: list[str] = []
    store.watch(current, lambda: calls.append("revoked"))
    assert calls == ["revoked"]


@pytest.mark.parametrize(
    ("values", "reason"),
    [
        pytest.param([], "missing", id="missing"),
        pytest.param([b"Bearer a", b"Bearer b"], "malformed", id="duplicate"),
        pytest.param([b"Basic abc"], "malformed", id="wrong-scheme"),
        pytest.param([b"Bearer " + b"a" * 5000], "malformed", id="oversized"),
        pytest.param([b"Bearer unknown-token"], "unknown_credential", id="unknown"),
    ],
)
def test_failure_reason_is_recorded_for_operators(values: list[bytes], reason: str) -> None:
    store = CredentialStore([])
    with pytest.raises(AuthenticationFailed) as excinfo:
        store.authenticate(values)
    assert excinfo.value.reason == reason
    assert str(excinfo.value) == "authentication failed"
