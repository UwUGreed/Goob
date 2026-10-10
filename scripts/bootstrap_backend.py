"""One-time operator provisioning; never an unauthenticated HTTP endpoint."""

import argparse
import json

from operations.persistence.database import engine_for, sessions
from operations.persistence.models import Branch, Membership, Tenant, uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--owner-subject", required=True, help="Verified OIDC subject, not email")
    parser.add_argument("--branch-name", default="Main branch")
    args = parser.parse_args()
    with sessions(engine_for())() as db:
        tenant, branch = uid(), uid()
        db.add(Tenant(id=tenant, name=args.name))
        db.flush()
        db.add(Branch(tenant_id=tenant, id=branch, name=args.branch_name))
        db.flush()
        db.add(
            Membership(
                tenant_id=tenant, subject=args.owner_subject, role="owner", branches=[branch]
            )
        )
        db.commit()
    print(
        json.dumps({"tenant_id": tenant, "branch_id": branch, "owner_subject": args.owner_subject})
    )


if __name__ == "__main__":
    main()
