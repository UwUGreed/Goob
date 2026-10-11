"""Opt-in browser QA; all writes live in conftest's disposable PostgreSQL schema."""
import os
from pathlib import Path
import subprocess
import threading
import time
from uuid import uuid4
import pytest
import uvicorn
from fastapi.responses import FileResponse, JSONResponse
from operations.api_v1.app import create_app
from operations.api_v1.portal_auth import password_hash
from operations.persistence.database import sessions
from operations.persistence.models import PortalUser, DispatchTechnician
from operations.domain import desk
from operations.domain.common import Actor
from test_invoice_editor import records, configured, line


@pytest.mark.skipif(os.environ.get("GOOB_BROWSER_CHECK") != "1",reason="Opt-in rendered browser QA")
def test_invoice_browser(api,engine,records,configured):
    identifier="invoice-browser-"+uuid4().hex+"@test.local"
    with sessions(engine)() as db:
        db.add(PortalUser(id=str(uuid4()),identifier=identifier,password_hash=password_hash("test-browser-password"),tenant_id=api.tenant,subject="owner",demo=True))
        location=desk.create(db,Actor(api.tenant,"owner","owner",("a","b")),"locations","a","Truck",{"location_type":"truck"})
        db.add(DispatchTechnician(tenant_id=api.tenant,id="plumber",branch_id="a",name="Test Plumber",trade="Plumbing",location_id=location.id,node="0-3",status="Available"));db.commit()
    unit=records["equipment_id"]
    job=api.create("jobs","Sink request",{"trade":"Plumbing","service":"repair","service_date":records["service_date"],"customer_approved":False,"billing_mode":"unknown","required_materials":[],"prerequisites":[],"lines":[],"currency":"USD"},customer_id=records["customer_id"],property_id=records["property_id"],equipment_id=unit)
    class MockGemini:
        def generate(self,source,context):
            lines=[line()] if source=="Sink is broken, needs repair 150$" else [line("Labor","150","labor","Labor $150"),line("Replacement valve","25","material","replacement valve $25")]
            return {"title":"Service charges","description":"Requested work","lines":lines,"missing_information":[],"ambiguities":[]},{"provider":"mock"}
    app=create_app(engine=engine,invoice_gemini=MockGemini())
    root=Path("goob-dispatch/dist").resolve()
    @app.get('/{path:path}')
    def frontend(path:str):
        candidate=(root/path).resolve()
        if path.startswith('api/'):
            return JSONResponse({'error':'Unknown API endpoint'},status_code=404)
        return FileResponse(candidate if candidate.is_relative_to(root) and candidate.is_file() else root/'index.html')
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=8092,log_level="error"))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.1)
        assert server.started
        env={**os.environ,"GOOB_INVOICE_TEST_USER":identifier,"GOOB_INVOICE_TEST_PASSWORD":"test-browser-password"}
        result=subprocess.run(['node','node_modules/@playwright/test/cli.js','test','--config','playwright.invoices.config.ts'],cwd='goob-dispatch',env=env,text=True,capture_output=True,timeout=150)
        assert result.returncode==0,result.stdout+result.stderr
    finally:
        server.should_exit=True;thread.join(timeout=10)
