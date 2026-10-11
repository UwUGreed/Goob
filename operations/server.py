import json
import os
import mimetypes
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from operations.db import connect
from operations.config import database_target
from operations.modules import crm, agreements, inventory, workflow
from operations.modules.registry import REGISTRY, guard, configure

ROOT = Path(__file__).parent
FRONTEND = ROOT.parent/'goob-dispatch'/'dist'
DATABASE = database_target()

def snapshot(db, tenant, role):
    result = {'simulation':True,'registry':REGISTRY}
    for name, reader in [('crm',crm.read),('agreements',agreements.read),('inventory',inventory.read)]:
        try:
            guard(db,tenant,role,name,'read')
            result[name] = reader(db,tenant)
        except ValueError:
            result[name] = None
    guard(db,tenant,role,'workflow','read')
    result['job'] = workflow.job(db,tenant)
    for table in ['proposals','invoices','audit']:
        result[table] = [dict(row) for row in db.execute(f'SELECT * FROM {table} WHERE tenant=?',(tenant,))]
    return result

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        legacy = {'/operations':'index.html', '/app.js':'app.js', '/style.css':'style.css'}
        if path == '/' and not (FRONTEND/'index.html').is_file():
            legacy['/'] = 'index.html'
        if path in legacy:
            filename = legacy[path]
            self.send_response(200)
            self.send_header('Content-Type',{'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[filename])
            self.end_headers()
            self.wfile.write((ROOT/'static'/filename).read_bytes())
            return
        if not path.startswith('/api/') and (FRONTEND/'index.html').is_file():
            target = (FRONTEND/(path.lstrip('/') or 'index.html')).resolve()
            if not target.is_relative_to(FRONTEND.resolve()) or not target.is_file():
                return self.reply(404,{'error':'Not found'})
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
            self.end_headers()
            self.wfile.write(target.read_bytes())
            return
        if self.path not in ['/api/state','/api/export']:
            return self.reply(404,{'error':'Not found'})
        db = connect(DATABASE, initialize=False)
        try:
            self.reply(200,snapshot(db,'demo',self.headers.get('X-Demo-Role','dispatcher')))
        except ValueError as error:
            self.reply(403,{'error':str(error)})
        finally:
            db.close()

    def do_POST(self):
        # Same-origin local demo only. Never accept browser cross-origin mutations.
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' or (self.headers.get('Origin') and self.headers['Origin'] != 'http://'+self.headers.get('Host','')):
            return self.reply(403,{'error':'Cross-origin command rejected'})
        db = connect(DATABASE, initialize=False)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if length < 0 or length > 4096:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body,dict):
                raise ValueError('Object required')
            role = self.headers.get('X-Demo-Role','dispatcher')
            if self.path == '/api/propose' and not body:
                result = workflow.propose(db,'demo',role)
            elif self.path == '/api/approve' and set(body) == {'id'} and isinstance(body['id'],str):
                result = workflow.approve(db,'demo',role,body['id'])
            elif self.path == '/api/modules' and set(body) == {'enabled'}:
                configure(db,'demo',role,body['enabled'])
                result = {'updated':True}
            else:
                raise ValueError('Unknown command or invalid fields')
            self.reply(200,result)
        except (ValueError,TypeError) as error:
            self.reply(400,{'error':str(error)})
        finally:
            db.close()

if __name__ == '__main__':
    db = connect(DATABASE)
    db.execute('SELECT 1 FROM tenants LIMIT 1')
    db.close()
    port = int(os.environ.get('GOOB_DEMO_PORT', '8081'))
    print(f'Goob workspace: http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
