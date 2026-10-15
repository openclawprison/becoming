"""Local, watchable, read-only web exploration. Python standard library only."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlsplit

from agent import Agent
from web_reader import Reader, normalize
from cognition import LocalMind


class Simulation:
    def __init__(self, path, seed=7, model='gemma3:1b'):
        self.path = Path(path)
        self.agent = Agent.load(path) if self.path.exists() else Agent(seed)
        self.reader = Reader()
        self.mind = LocalMind(model) if model else None
        self.reflect_requested = False
        self.agent.data['cognition'].update({'mode': 'local_language_model' if model else 'word_learning_only',
            'model': model or None, 'pretrained_knowledge': bool(model)})
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
                reflect_only = self.reflect_requested
                self.reflect_requested = False
                if not self.running and not reflect_only:
                    continue
                page = self.agent.data['last_page'] if reflect_only else None
                item = None if reflect_only else self.agent.choose()
                if not reflect_only and item is None:
                    self.running = False
                    self.status = 'No unvisited links remain. Add another starting URL.'
                    self.agent.save(self.path)
                    continue
                self.busy = True
                self.status = 'Reflecting on the last page' if reflect_only else 'Reading '+item['url']
            # No lock during network requests: pause/status remain responsive.
            try:
                if not reflect_only:
                    page = self.reader.fetch(item['url'])
                    with self.lock:
                        self.agent.experience(page, item)
                        self.agent.save(self.path)
                        self.status = 'Observed '+page['url']
                if self.mind and page:
                    with self.lock:
                        step = self.agent.data['tick']
                        already = step in self.agent.data['reflected_steps']
                        history, interests = self.agent.cognitive_context()
                        traits = self.agent.data['traits'].copy()
                        self.status = 'Reading for meaning with local '+self.mind.model
                    if not already:
                        try:
                            result = self.mind.reflect(page, history, interests, traits)
                            with self.lock:
                                self.agent.integrate(result, page, step)
                                self.status = 'Reflection recorded: '+page['title']
                        except Exception as error:
                            with self.lock:
                                self.agent.data['cognition']['error'] = str(error)[:200]
                                self.agent.event('reflection_failed', detail=str(error)[:200])
                                self.status = 'Page retained; comprehension unavailable: '+str(error)[:160]
                                # Avoid repeated heavy failures; explicit resume retries next page.
                                self.running = False
            except Exception as error:
                with self.lock:
                    if item:
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
                    elif path == '/api/reflect':
                        if body or not sim.mind:
                            raise ValueError('Local model required; no arguments accepted')
                        if sim.busy or sim.reflect_requested:
                            raise ValueError('An experience is already in progress')
                        if not sim.agent.data['last_page']:
                            raise ValueError('Read a page first')
                        if sim.agent.data['tick'] in sim.agent.data['reflected_steps']:
                            raise ValueError('This page already has a saved reflection')
                        sim.reflect_requested = True
                        sim.status = 'Reflection queued'
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
    parser.add_argument('--model', default='gemma3:1b', help='Already-installed local Ollama model')
    parser.add_argument('--no-model', action='store_true', help='Use the limited word learner only')
    args = parser.parse_args()
    sim = Simulation(args.save, args.seed, model=None if args.no_model else args.model)
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
        worker.join(310)
        with sim.lock:
            sim.agent.save(sim.path)
        server.server_close()


if __name__ == '__main__':
    main()
