"""Bearer authentication across both TC-048 profiles.

A bearer token is first looked up among the operator-issued application
credentials. If it is not one of them and OAuth is configured, it is validated
as an access token. Either way, every failure is the same ``401``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from grenslan.server.auth import ApplicationCredential, AuthenticationFailed, CredentialStore, bearer_token
from grenslan.server.oauth import AccessTokenValidator, InvalidAccessToken, TokenPrincipal

Principal = ApplicationCredential | TokenPrincipal


class Authenticator:
    def __init__(self, credentials: CredentialStore, tokens: AccessTokenValidator | None = None) -> None:
        self.credentials = credentials
        self.tokens = tokens

    def authenticate(self, authorization: Sequence[bytes]) -> Principal:
        token = bearer_token(authorization)
        credential = self.credentials.lookup(token)
        if credential is not None:
            return credential
        if self.tokens is None:
            raise AuthenticationFailed("unknown_credential")
        try:
            return self.tokens.validate(token.decode("ascii"))
        except InvalidAccessToken as error:
            # A value that is not JWT-shaped was meant as an application credential.
            reason = "unknown_credential" if error.reason == "malformed" else f"token_{error.reason}"
            raise AuthenticationFailed(reason) from None

    def watch(self, principal: Principal, callback: Callable[[], None]) -> Callable[[], None]:
        """Call ``callback`` once if the principal is revoked or its grant changes."""
        if isinstance(principal, TokenPrincipal):
            if self.tokens is None:
                callback()
                return lambda: None
            return self.tokens.watch(principal, callback)
        return self.credentials.watch(principal, callback)

    def challenge(self, *, token_presented: bool) -> str:
        """The ``WWW-Authenticate`` value for a 401 (RFC 6750, RFC 9728)."""
        parameters = ['realm="grenslan"']
        if self.tokens is not None:
            parameters.append(f'resource_metadata="{self.tokens.metadata_url}"')
        if token_presented:
            parameters.append('error="invalid_token"')
        return "Bearer " + ", ".join(parameters)
