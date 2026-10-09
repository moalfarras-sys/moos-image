"""Bounded HTTPS client; secrets never enter URLs, redirects, errors or disk."""
import ipaddress
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE = 3 * 1024 * 1024


class ApiError(Exception):
    def __init__(self, code, status=0):
        super().__init__(code)
        self.code, self.status = code, status


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Authorization must never follow a server-supplied destination.
        raise ApiError('redirect_refused', code)


class Api:
    def __init__(self, endpoint, *, review=False, timeout=15):
        parsed = urllib.parse.urlsplit(endpoint)
        try:
            loopback = ipaddress.ip_address(parsed.hostname or '').is_loopback
        except ValueError:
            loopback = False
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path not in ('', '/')
                or (parsed.scheme != 'https' and not (review and loopback and parsed.scheme == 'http'))):
            raise ValueError('one HTTPS service origin required')
        self.endpoint = endpoint.rstrip('/')
        if not 1 <= timeout <= 120:
            raise ValueError('bounded request timeout required')
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects(),
                         urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(self, method, path, *, token=None, body=None, binary=None, retry_id=None):
        if not re.fullmatch(r'/v1/[A-Za-z0-9_/?=&.:-]+', path):
            raise ApiError('invalid_request')
        headers = {'Accept':'application/json', 'User-Agent':'MoOS-Participation/1'}
        if token:
            if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
                raise ApiError('sign_in_required')
            headers['Authorization'] = 'Bearer '+token
        if retry_id:
            headers['Idempotency-Key'] = retry_id
        data = binary
        if body is not None:
            data = json.dumps(body,ensure_ascii=False).encode()
            headers['Content-Type'] = 'application/json'
        elif binary is not None:
            headers['Content-Type'] = 'application/octet-stream'
        request = urllib.request.Request(self.endpoint+path,data=data,headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE+1)
                if len(raw)>MAX_RESPONSE:
                    raise ApiError('invalid_response')
                if response.status == 204:
                    return {'schema':1}
                if path.startswith('/v1/images/'):
                    if response.headers.get_content_type() != 'image/png' or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                        raise ApiError('invalid_image')
                    return raw
        except urllib.error.HTTPError as error:
            try:
                raw = error.read(4096)
            finally:
                error.close()
            try:
                detail = json.loads(raw).get('detail',{})
                code = detail.get('code','invalid_request') if isinstance(detail,dict) else 'invalid_request'
                if not isinstance(code,str) or not re.fullmatch(r'[a-z_]{1,64}',code):
                    code = 'invalid_request'
            except (ValueError,AttributeError):
                code = 'service_unavailable'
            raise ApiError(code,error.code) from None
        except (urllib.error.URLError,OSError,TimeoutError):
            raise ApiError('offline') from None
        try:
            payload = json.loads(raw)
        except (ValueError,TypeError):
            raise ApiError('invalid_response') from None
        if not isinstance(payload,dict) or type(payload.get('schema')) is not int or payload['schema'] != 1:
            raise ApiError('invalid_response')
        return payload
