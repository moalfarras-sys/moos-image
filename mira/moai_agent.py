"""Mo AI's agent workspace API (moai-agent-api, 127.0.0.1:$MOAI_AGENT_PORT, default 8077).

The Workbench and the approvals inbox read and drive it: projects, files, Git status and diff,
tasks, the owner's own terminal, agent sessions, the approvals queue, readiness and the (read-only)
configuration. Every request carries the X-Moai-Agent header the service requires, never goes
through a proxy and never follows a redirect. Errors come back as {'error': ...} with the class name
or the service's own short reason — never a traceback, never a secret.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

PORT = int(os.environ.get('MOAI_AGENT_PORT', '8077'))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def request(method, path, body=None, query=None, timeout=15):
    url = f'http://127.0.0.1:{PORT}{path}'
    if query:
        url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'X-Moai-Agent': '1', 'Content-Type': 'application/json'})
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        try:
            payload = json.load(err)
        except ValueError:
            payload = {}
        return {'error': payload.get('error') if isinstance(payload, dict) and payload.get('error') else f'http_{err.code}'}
    except (urllib.error.URLError, OSError, ValueError) as err:
        return {'error': 'agent_unreachable', 'detail': type(err).__name__}


def get(path, **query):
    return request('GET', path, query=query or None)


def post(path, body):
    return request('POST', path, body=body)
