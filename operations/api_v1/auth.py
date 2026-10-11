import os

import jwt

from operations.domain.common import Problem


class OIDCVerifier:
    """Issuer/JWKS are administrator configuration; never derived from the token."""

    def __init__(self):
        self.issuer = os.environ.get("OIDC_ISSUER", "")
        self.audience = os.environ.get("OIDC_AUDIENCE", "")
        url = os.environ.get("OIDC_JWKS_URL", "")
        if (
            not self.issuer.startswith("https://")
            or not url.startswith("https://")
            or not self.audience
        ):
            raise RuntimeError("Configure HTTPS OIDC_ISSUER, OIDC_JWKS_URL and OIDC_AUDIENCE.")
        self.keys = jwt.PyJWKClient(url, timeout=5, cache_jwk_set=True, lifespan=300)

    def __call__(self, token):
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            if not isinstance(payload["sub"], str) or not payload["sub"]:
                raise ValueError("Missing subject")
            return payload["sub"]
        except (jwt.PyJWTError, ValueError) as exc:
            raise Problem("Invalid or expired access token.", 401) from exc
