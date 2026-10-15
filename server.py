"""Local, watchable, read-only web exploration. Python standard library only."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit

from agent import Agent
from web_reader import Reader, normalize


class Simulation:
    def __init__(self, path, seed=7):
        self.path = Path(path)
        self.agent = Agent.load(path) if self.path.exists() else Agent(seed)
        self.reader = Reader()
        self.lock = threading.RLock()
        self.running = False
        self.busy = False
        self.status = 'Waiting for a starting URL'
        self.stop = threading.Event()

    def snapshot(self):
        return {**self.agent.snapshot(), 'running': self.running, 'busy': self.busy, 'status': self.status}

    def worker(self):
        while not self.stop.wait(2):
            with self.lock:
                if not self.running:
                    continue
                item = self.agent.choose()
                if item is None:
                    self.running = False
                    self.status = 'No unvisited links remain. Add another starting URL.'
                    self.agent.save(self.path)
                    continue
                self.busy = True
                self.status = 'Reading '+item['url']
            # No lock during network requests: pause/status remain responsive.
            try:
                page = self.reader.fetch(item['url'])
                with self.lock:
                    self.agent.experience(page, item)
                    self.status = 'Observed '+page['url']
            except Exception as error:
                with self.lock:
                    self.agent.fail(item, error)
                    self.status = str(error)[:200]
            finally:
                with self.lock:
                    self.busy = False
                    try:
                        self.agent.save(self.path)
                    except OSError as error:
                        self.running = False
                        self.status = 'Save failed: '+str(error)


def handler(sim):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, value, kind='application/json; charset=utf-8'):
            payload = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-src 'none'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def local(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.local():
                self.reply(403, {'error': 'Local Host required'})
                return
            path = urlsplit(self.path).path
            if path == '/':
                self.reply(200, Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/api/state':
                with sim.lock:
                    self.reply(200, sim.snapshot())
            elif path == '/api/export':
                with sim.lock:
                    sim.agent.save(sim.path)
                    self.reply(200, sim.path.read_bytes())
            else:
                self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.local() or (origin and origin != 'http://'+self.headers.get('Host', '')):
                self.reply(403, {'error': 'Local same-origin requests required'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.reply(415, {'error': 'JSON required'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 8192:
                    raise ValueError('Request too large')
                body = json.loads(self.rfile.read(size) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                path = urlsplit(self.path).path
                with sim.lock:
                    if path == '/api/seed':
                        if set(body) != {'url'}:
                            raise ValueError('url required')
                        sim.agent.seed(normalize(body['url']))
                        sim.status = 'Starting location added; press Begin'
                    elif path == '/api/control':
                        if set(body) != {'running'} or type(body['running']) is not bool:
                            raise ValueError('running must be boolean')
                        sim.running = body['running']
                        sim.status = 'Exploring' if sim.running else 'Paused; any in-flight read will finish'
                    elif path == '/api/recall':
                        if set(body) != {'question'} or not isinstance(body['question'], str) or len(body['question']) > 1000:
                            raise ValueError('question must be text, at most 1000 characters')
                        self.reply(200, {'passages': sim.agent.recall(body['question'])})
                        return
                    elif path == '/api/save':
                        if body:
                            raise ValueError('No save arguments')
                    else:
                        self.reply(404, {'error': 'Not found'})
                        return
                    sim.agent.save(sim.path)
                    self.reply(200, sim.snapshot())
            except (ValueError, TypeError, OSError) as error:
                self.reply(400, {'error': str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8890)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--save', default='data/becoming.json')
    args = parser.parse_args()
    sim = Simulation(args.save, args.seed)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(sim))
    worker = threading.Thread(target=sim.worker, daemon=True)
    worker.start()
    print(f'Becoming: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sim.stop.set()
        worker.join(60)
        with sim.lock:
            sim.agent.save(sim.path)
        server.server_close()


if __name__ == '__main__':
    main()
