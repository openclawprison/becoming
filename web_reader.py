"""Bounded, public HTTP(S), GET-only page reader; never executes page code."""
import http.client
import gzip
import io
from html.parser import HTMLParser
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.robotparser import RobotFileParser

USER_AGENT = 'BecomingResearchBot/0.1'


def normalize(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('URL must be text, at most 2048 characters')
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Public http/https URLs without credentials required')
    if p.port not in (None, 80, 443):
        raise ValueError('Only standard web ports allowed')
    if any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError('Control characters/whitespace in URL')
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))


def public_addresses(host, port):
    rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(row[4][0] for row in rows))
    if not addresses or any(not ipaddress.ip_address(ip).is_global
                            or ipaddress.ip_address(ip).is_multicast
                            or ipaddress.ip_address(ip).is_reserved for ip in addresses):
        raise ValueError('Private, local, multicast and reserved addresses are blocked')
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, port):
        super().__init__(host, port, timeout=8, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class Document(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url, self.parts, self.title, self.links = url, [], [], []
        self.hidden = 0
        self.in_title = False
        self.anchor = None
        self.main_parts, self.main_links = [], []
        self.main_container, self.main_depth = None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'template', 'svg'):
            self.hidden += 1
        if self.hidden:
            return
        attrs = dict(attrs)
        if self.main_depth and tag == self.main_container:
            self.main_depth += 1
        elif not self.main_depth and (tag in ('main', 'article') or attrs.get('role') == 'main'):
            self.main_container, self.main_depth = tag, 1
        if tag == 'title':
            self.in_title = True
        if tag == 'a' and attrs.get('href'):
            try:
                self.anchor = {'url': normalize(urljoin(self.url, attrs['href'])), 'label': ''}
            except ValueError:
                self.anchor = None
        if tag in ('p', 'br', 'div', 'h1', 'h2', 'li'):
            self.parts.append('\n')
            if self.main_depth:
                self.main_parts.append('\n')

    def handle_endtag(self, tag):
        if not self.hidden and tag in ('p', 'div', 'h1', 'h2', 'li', 'article', 'main'):
            self.parts.append('\n')
            if self.main_depth:
                self.main_parts.append('\n')
        if tag in ('script', 'style', 'noscript', 'template', 'svg') and self.hidden:
            self.hidden -= 1
        if tag == 'title':
            self.in_title = False
        if tag == 'a' and self.anchor:
            if len(self.links) < 100:
                self.anchor['label'] = self.anchor['label'].strip()[:200]
                self.links.append(self.anchor)
                if self.main_depth:
                    self.main_links.append(self.anchor)
            self.anchor = None
        if self.main_depth and tag == self.main_container:
            self.main_depth -= 1

    def handle_data(self, text):
        if self.hidden:
            return
        self.parts.append(text)
        if self.main_depth:
            self.main_parts.append(text)
        if self.in_title:
            self.title.append(text)
        if self.anchor:
            self.anchor['label'] += text[:200]


class Reader:
    def __init__(self):
        self.robots = {}
        self.last_request = {}

    def request(self, url):
        p = urlsplit(normalize(url))
        port = p.port or (443 if p.scheme == 'https' else 80)
        ips = public_addresses(p.hostname, port)
        delay = 2-(time.monotonic()-self.last_request.get(p.hostname, 0))
        if delay > 0:
            time.sleep(delay)
        self.last_request[p.hostname] = time.monotonic()
        if len(self.last_request) > 512:
            del self.last_request[next(iter(self.last_request))]
        if p.scheme == 'https':
            conn = PinnedHTTPS(p.hostname, ips[0], port)
        else:
            conn = http.client.HTTPConnection(ips[0], port, timeout=8)
        try:
            conn.request('GET', urlunsplit(('', '', p.path or '/', p.query, '')),
                         headers={'Host': p.netloc, 'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            body = response.read(512001)
            if len(body) > 512000:
                raise ValueError('Page exceeds 512 KB limit')
            headers = dict((k.lower(), v) for k, v in response.getheaders())
            encoding = headers.get('content-encoding', 'identity').lower()
            if encoding == 'gzip':
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                    body = compressed.read(512001)
                if len(body) > 512000:
                    raise ValueError('Expanded page exceeds 512 KB limit')
            elif encoding != 'identity':
                raise ValueError('Unsupported content encoding')
            return response.status, headers, body
        finally:
            conn.close()

    def allowed(self, url):
        p = urlsplit(url)
        origin = urlunsplit((p.scheme, p.netloc, '', '', ''))
        if origin not in self.robots:
            status, _, body = self.request(origin+'/robots.txt')
            parser = RobotFileParser()
            if status == 404:
                parser.parse([])
            elif status == 200:
                parser.parse(body.decode('utf8', errors='replace').splitlines())
            else:
                # Fail closed for unavailable/redirected robots rules.
                parser.disallow_all = True
            if len(self.robots) >= 512:
                del self.robots[next(iter(self.robots))]
            self.robots[origin] = (time.monotonic(), parser)
        stamp, parser = self.robots[origin]
        if time.monotonic()-stamp > 3600:
            del self.robots[origin]
            return self.allowed(url)
        delay = parser.crawl_delay(USER_AGENT) or 2
        pause = min(60, delay)-(time.monotonic()-self.last_request.get(p.hostname, 0))
        if delay > 60:
            raise ValueError('Site requires crawl delay above supported limit')
        if pause > 0:
            time.sleep(pause)
        return parser.can_fetch(USER_AGENT, url)

    def fetch(self, url):
        url = normalize(url)
        for _ in range(6):
            if not self.allowed(url):
                raise ValueError('robots.txt does not allow this page')
            status, headers, body = self.request(url)
            if status in (301, 302, 303, 307, 308):
                url = normalize(urljoin(url, headers.get('location', '')))
                continue
            if status != 200:
                raise ValueError(f'HTTP {status}')
            kind = headers.get('content-type', '').split(';')[0].strip()
            if kind not in ('text/html', 'text/plain'):
                raise ValueError('Only HTML and plain text are read')
            text = body.decode('utf8', errors='replace')
            doc = Document(url)
            if kind == 'text/html':
                doc.feed(text)
                text = '\n'.join(' '.join(line.split()) for line in ''.join(doc.main_parts or doc.parts).splitlines() if line.strip())
            return {'url': url, 'title': ''.join(doc.title).strip()[:200] or url,
                    'text': text[:40000], 'links': doc.main_links or doc.links}
        raise ValueError('Too many redirects')
