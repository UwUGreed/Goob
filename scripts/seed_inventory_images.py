"""Attach bundled licensed photos to matching demo SKUs without touching stock."""
import json
from pathlib import Path
from sqlalchemy import select
from operations.persistence.database import engine_for, sessions
from operations.persistence.models import PortalUser, Record
from operations.api_v1.schemas import SKU

def seed(db):
    sources=json.loads(Path("goob-dispatch/public/inventory-images/sources.json").read_text())
    demo_tenants=select(PortalUser.tenant_id).where(PortalUser.demo.is_(True))
    changed=0
    for row in db.scalars(select(Record).where(Record.tenant_id.in_(demo_tenants),Record.kind=="skus",Record.archived.is_(False)).with_for_update()):
        if row.name not in sources or row.data.get("image_url"): continue
        fields={k:v for k,v in sources[row.name].items() if k!="license_url"}
        if not Path("goob-dispatch/public"+fields["image_url"]).is_file():
            raise RuntimeError("Bundled inventory image is missing.")
        row.data=SKU.model_validate(row.data|fields).model_dump();row.revision+=1;changed+=1
    db.commit()
    return changed

if __name__=="__main__":
    from dotenv import load_dotenv
    load_dotenv(".env");load_dotenv("goob-dispatch/.env.local")
    with sessions(engine_for())() as db: print("Demo SKU images attached:",seed(db))
