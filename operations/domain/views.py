"""Finite, presentation-only preferences scoped to authenticated workspace identity."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from operations.domain.common import Problem
from operations.persistence.models import ViewPreference

PAGES = {"overview", "dispatch", "customers", "jobs", "inventory", "memberships", "invoices", "growth", "stock-ledger", "work-review", "migration"}
SECTIONS = {"inventory": {"summary", "attention", "ledger"}, "overview": {"summary"}, "dispatch": {"simulation"}}
class Appearance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    density: Literal["comfortable", "compact"] = "comfortable"
    presentation: Literal["list", "card"] = "list"
    theme: Literal["fieldbook", "after-hours", "workshop"] = "fieldbook"
    columns: list[Literal["image", "trade", "reserved", "on_hand", "threshold"]] = Field(default_factory=lambda:["image","trade","reserved","on_hand"], max_length=5)
    sections: list[Literal["summary", "attention", "ledger", "simulation"]] = Field(default_factory=list, max_length=4)
    hidden: list[Literal["summary", "attention", "ledger", "simulation"]] = Field(default_factory=list, max_length=4)
    dispatch_names: bool = True
    dispatch_routes: bool = True
    dispatch_status: Literal["All", "Unassigned", "Assigned", "En route", "Arrived", "Working", "Completed"] = "All"

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: str = Field(default="Default", min_length=1, max_length=50)
    views: dict[str, Appearance] = Field(max_length=12)
    @model_validator(mode="after")
    def valid_names(self):
        if self.active not in self.views or any(not n.strip() or len(n)>50 for n in self.views):
            raise ValueError("Choose an existing named view; names must be 1–50 characters.")
        return self

def defaults(page):
    return {"active":"Default", "views":{"Default": Appearance(sections=[s for s in ("summary","attention","ledger","simulation") if s in SECTIONS.get(page,set())]).model_dump()}}

def read(db, actor, page):
    if page not in PAGES: raise Problem("Unknown view page.",404)
    personal = db.get(ViewPreference,(actor.tenant,actor.subject,page))
    company = db.get(ViewPreference,(actor.tenant,"@company",page))
    return {"settings": personal.settings if personal else company.settings if company else defaults(page),
        "revision": personal.revision if personal else 0,
        "company_revision": company.revision if company else 0,
        "company_settings": company.settings if company else defaults(page),
        "personal_override": bool(personal), "can_set_company": actor.role=="owner"}

def save(db, actor, page, payload):
    read(db,actor,page)
    company = payload.get("company",False)
    if type(company) is not bool: raise Problem("Invalid preference scope.",422)
    if company and actor.role != "owner": raise Problem("Owner permission required for company defaults.",403)
    subject = "@company" if company else actor.subject
    row = db.get(ViewPreference,(actor.tenant,subject,page),with_for_update=True)
    if payload.get("expected_revision") != (row.revision if row else 0):
        raise Problem("Saved view changed. Reload before saving.",409)
    if payload.get("inherit") is True and not company:
        if row: db.delete(row);db.flush()
        return read(db,actor,page)
    try: settings=Settings.model_validate(payload.get("settings")).model_dump()
    except ValueError: raise Problem("Invalid view settings. Use the supported choices.",422) from None
    for view in settings["views"].values():
        allowed=SECTIONS.get(page,set())
        if set(view["sections"])!=allowed or not set(view["hidden"])<=allowed or any(len(view[k])!=len(set(view[k])) for k in ("columns","sections","hidden")):
            raise Problem("Invalid optional sections or duplicate columns.",422)
        if page not in {"inventory","jobs"} and view["presentation"]!="list":
            raise Problem("Card presentation is available on Inventory and Jobs.",422)
    if not row:
        row=ViewPreference(tenant_id=actor.tenant,subject=subject,page=page,revision=0)
        db.add(row)
    row.settings=settings;row.revision+=1;db.flush()
    return read(db,actor,page)
