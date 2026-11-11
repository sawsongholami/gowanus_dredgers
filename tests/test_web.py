"""The shared web helper retries timeouts and server errors.

Runs against a tiny local server that misbehaves on its first answers,
so no outside site is touched.
"""
import http.server
import pathlib as pl
import sys
import threading
import time

import pytest
import requests

sys.path.insert(0, str(pl.Path(__file__).parent.parent / 'data_import'))

import web  # noqa: E402


class FlakyHandler(http.server.BaseHTTPRequestHandler):
    """Plays back server.script: one entry per request, then 200 'ok'.
    An int is a status code to return; 'slow' stalls past the timeout."""

    def do_GET(self):
        self.server.calls += 1
        step = self.server.script.pop(0) if self.server.script else 200
        if step == 'slow':
            time.sleep(1)
            step = 200
        body = b'ok' if step == 200 else b'error'
        try:
            self.send_response(step)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client already gave up on this one

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FlakyHandler)
    srv.calls = 0
    srv.script = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def url(srv):
    return f'http://127.0.0.1:{srv.server_address[1]}/'


def test_retries_server_errors(server):
    server.script = [503, 502]
    resp = web.make_session(backoff=0).get(url(server), timeout=5)
    assert resp.status_code == 200 and resp.text == 'ok'
    assert server.calls == 3


def test_retries_a_read_timeout(server):
    server.script = ['slow']
    resp = web.make_session(backoff=0).get(url(server), timeout=0.3)
    assert resp.text == 'ok'
    assert server.calls == 2


def test_gives_up_and_returns_the_last_error(server):
    server.script = [503] * 10
    resp = web.make_session(retries=2, backoff=0).get(url(server), timeout=5)
    assert resp.status_code == 503
    assert server.calls == 3


def test_gives_up_on_timeouts_with_an_error(server):
    server.script = ['slow'] * 10
    with pytest.raises(requests.exceptions.ConnectionError):
        web.make_session(retries=1, backoff=0).get(url(server), timeout=0.3)
    assert server.calls == 2


def test_does_not_retry_a_missing_page(server):
    server.script = [404]
    resp = web.make_session(backoff=0).get(url(server), timeout=5)
    assert resp.status_code == 404
    assert server.calls == 1


def test_get_sets_a_default_timeout(monkeypatch):
    seen = {}
    monkeypatch.setattr(web._session, 'get', lambda u, **kw: seen.update(kw))
    web.get('https://example.invalid')
    assert seen['timeout'] == web.DEFAULT_TIMEOUT
