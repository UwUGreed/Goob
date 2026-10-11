"""Read-only hosted API smoke test. Pass credentials through environment variables."""

import argparse
import ipaddress
import json
import os
from urllib.parse import quote, urlsplit

import httpx


def validate_url(value):
    try:
        url = urlsplit(value)
        local = url.hostname == "localhost"
        if not local:
            try:
                local = ipaddress.ip_address(url.hostname or "").is_loopback
            except ValueError:
                pass
        valid = (
            url.hostname
            and url.port != 0
            and (url.scheme == "https" or url.scheme == "http" and local)
        )
        if (
            not valid
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError
    except ValueError:
        raise ValueError(
            "Use an HTTPS server origin, or HTTP loopback for local testing."
        ) from None
    return value.rstrip("/")


def check(client, headers, job_id=None):
    results = []

    def expect(path, status=200, authenticated=False):
        response = client.get(path, headers=headers if authenticated else {})
        if response.status_code != status:
            raise ValueError(
                f"Unexpected HTTP status for {path.split('?')[0]}: {response.status_code}"
            )
        if "application/json" not in response.headers.get("content-type", ""):
            raise ValueError("API returned non-JSON content; check reverse-proxy routing.")
        return response.json()

    assert_status = expect("/health/live")
    if assert_status.get("status") != "live":
        raise ValueError("Liveness response was invalid.")
    if expect("/health/ready").get("status") != "ready":
        raise ValueError("Readiness response was invalid.")
    results.append("liveness_and_schema_readiness")
    expect("/api/v1/me", status=401)
    results.append("anonymous_access_rejected")
    identity = expect("/api/v1/me", authenticated=True)
    if identity.get("tenant_id") != headers.get("X-Tenant-ID") or not identity.get("branches"):
        raise ValueError(
            "Identity response does not match the requested company and branch access."
        )
    results.append("authenticated_company_access")
    if job_id:
        workspace = expect(f"/api/v1/jobs/{quote(job_id, safe='')}/workspace", authenticated=True)
        if workspace.get("job", {}).get("id") != job_id:
            raise ValueError("Workspace returned the wrong job.")
        results.append("persisted_job_workspace")
    return {"passed": results, "mutations_performed": False, "providers_tested": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, type=validate_url)
    parser.add_argument("--job-id")
    args = parser.parse_args()
    token, tenant = os.environ.get("GOOB_ACCESS_TOKEN"), os.environ.get("GOOB_TENANT_ID")
    if not token or not tenant:
        parser.error("Set GOOB_ACCESS_TOKEN and GOOB_TENANT_ID in the environment.")
    headers = {"Authorization": "Bearer " + token, "X-Tenant-ID": tenant}
    try:
        with httpx.Client(base_url=args.url, timeout=20, follow_redirects=False) as client:
            result = check(client, headers, args.job_id)
    except (httpx.HTTPError, ValueError):
        print(
            json.dumps(
                {
                    "passed": False,
                    "error": "API verification failed; check health, routing, token, company and job access.",
                }
            )
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
