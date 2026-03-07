import base64
import hashlib
import urllib.parse

def b64d(s):
    s = s.strip().replace('-', '+').replace('_', '/')
    s += '=' * (-len(s) % 4)
    return base64.b64decode(s).decode(errors='replace')

def uri_hash(uri):
    u = uri.strip()
    if '#' in u: u = u[:u.rindex('#')]
    return hashlib.md5(u.encode()).hexdigest()[:16]

def _sr(s):
    if '#' in s:
        s, r = s.rsplit('#', 1)
        return s, urllib.parse.unquote(r)
    return s, ''

def _sp(s):
    if '?' in s:
        s2, q = s.split('?', 1)
        return s2, dict(urllib.parse.parse_qsl(q))
    return s, {}

def _hp(s):
    if s.startswith('['):
        i = s.index(']')
        return s[1:i], int(s[i+2:])
    h, p = s.rsplit(':', 1)
    return h, int(p)

def _srv_name(srv, maxlen=38):
    return (srv['remark'] or f"{srv['host']}:{srv['port']}")[:maxlen]
