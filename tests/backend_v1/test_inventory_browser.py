import os
from pathlib import Path
import subprocess,threading,time
from uuid import uuid4
import pytest,uvicorn
from fastapi.responses import FileResponse,JSONResponse
from operations.api_v1.app import create_app
from operations.api_v1.portal_auth import password_hash
from operations.persistence.database import sessions
from operations.persistence.models import PortalUser

@pytest.mark.skipif(os.environ.get('GOOB_BROWSER_CHECK')!='1',reason='Opt-in browser QA')
def test_inventory_browser(api,engine):
    user='inventory-browser-'+uuid4().hex+'@test.local'
    with sessions(engine)() as db:
        db.add(PortalUser(id=str(uuid4()),identifier=user,password_hash=password_hash('test-browser-password'),tenant_id=api.tenant,subject='owner',demo=True));db.commit()
    location=api.create('locations','Warehouse',{'location_type':'warehouse'})
    sources=__import__('json').loads(Path('goob-dispatch/public/inventory-images/sources.json').read_text())
    for n,(name,fields) in enumerate(sources.items()):
        sku=api.create('skus',name,{'barcode':'PHOTO-'+str(n),'trade':'Electrical' if 'Circuit' in name else 'HVAC' if 'capacitor' in name else 'Plumbing',**{k:v for k,v in fields.items() if k!='license_url'}})
        api.request('POST','/inventory/commands',{'action':'receive','sku_id':sku['id'],'location_id':location['id'],'quantity':8,'reason':'Initial inventory'})
        api.request('POST','/inventory/commands',{'action':'threshold','sku_id':sku['id'],'location_id':location['id'],'minimum':10,'target':20,'reason':'Reorder level'})
    app=create_app(engine=engine)
    root=Path('goob-dispatch/dist').resolve()
    @app.get('/{path:path}')
    def frontend(path:str):
        candidate=(root/path).resolve()
        if path.startswith('api/'):return JSONResponse({'error':'Unknown API'},status_code=404)
        return FileResponse(candidate if candidate.is_relative_to(root) and candidate.is_file() else root/'index.html')
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8093,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.1)
        assert server.started
        env={**os.environ,'GOOB_INVENTORY_TEST_USER':user}
        result=subprocess.run(['node','node_modules/@playwright/test/cli.js','test','--config','playwright.views.config.ts'],cwd='goob-dispatch',env=env,text=True,capture_output=True,timeout=120)
        assert result.returncode==0,result.stdout+result.stderr
    finally:
        server.should_exit=True;thread.join(timeout=10)
