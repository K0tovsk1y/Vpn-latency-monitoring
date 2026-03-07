import json
import urllib.request
from .utils import b64d, _sr, _sp, _hp

def fetch_sub(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'v2rayN/7.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode(errors='replace')
    try: raw = b64d(raw)
    except: pass
    return [l.strip() for l in raw.splitlines() if '://' in l]


def parse_uri(uri):
    uri = uri.strip()
    try:
        if uri.startswith('vless://'):
            r = uri[8:]; r, rem = _sr(r); r, par = _sp(r)
            uid, hs = r.split('@', 1); h, p = _hp(hs)
            return dict(protocol='vless', host=h, port=p,
                        remark=rem, transport=par.get('type','tcp'), raw=uri)
        if uri.startswith('vmess://'):
            j = json.loads(b64d(uri[8:]))
            return dict(protocol='vmess', host=j.get('add',''),
                        port=int(j.get('port',0)), remark=j.get('ps',''),
                        transport=j.get('net','tcp'), raw=uri)
        if uri.startswith('trojan://'):
            r = uri[9:]; r, rem = _sr(r); r, par = _sp(r)
            pw, hs = r.split('@', 1); h, p = _hp(hs)
            return dict(protocol='trojan', host=h, port=p,
                        remark=rem, transport=par.get('type','tcp'), raw=uri)
        if uri.startswith('ss://'):
            r = uri[5:]; r, rem = _sr(r)
            if '@' in r: _, hs = r.split('@', 1)
            else: _, hs = b64d(r).rsplit('@', 1)
            h, p = _hp(hs.split('?')[0] if '?' in hs else hs)
            return dict(protocol='ss', host=h, port=p,
                        remark=rem, transport='tcp', raw=uri)
        if uri.startswith(('hy2://','hysteria2://')):
            pfx = 'hy2://' if uri.startswith('hy2://') else 'hysteria2://'
            r = uri[len(pfx):]; r, rem = _sr(r); r, par = _sp(r)
            pw, hs = r.split('@', 1); h, p = _hp(hs)
            return dict(protocol='hy2', host=h, port=p,
                        remark=rem, transport='quic', raw=uri)
    except: pass
    return None


def _stream(params):
    net = params.get('type', params.get('net', 'tcp'))
    sec = params.get('security', params.get('tls', 'none')) or 'none'
    ss = {"network": net, "security": sec}
    if sec == 'reality':
        ss['realitySettings'] = {
            "fingerprint": params.get('fp','chrome'),
            "publicKey": params.get('pbk',''),
            "serverName": params.get('sni',''),
            "shortId": params.get('sid',''),
            "spiderX": params.get('spx','/')}
    elif sec == 'tls':
        tls = {"serverName": params.get('sni',''),
               "fingerprint": params.get('fp','chrome'),
               "allowInsecure": params.get('allowInsecure','')=='1'}
        alpn = params.get('alpn','')
        if alpn: tls['alpn'] = alpn.split(',')
        ss['tlsSettings'] = tls
    if net == 'ws':
        ss['wsSettings'] = {"path": params.get('path','/'),
            "headers": {"Host": params.get('host','')}}
    elif net == 'grpc':
        ss['grpcSettings'] = {"serviceName": params.get('serviceName',''),
            "multiMode": params.get('mode','') == 'multi'}
    elif net in ('h2','http'):
        ss['httpSettings'] = {"path": params.get('path','/'),
            "host": [x for x in [params.get('host','')] if x]}
    elif net in ('xhttp','splithttp'):
        ss['network'] = 'splithttp'
        ss['splithttpSettings'] = {"path": params.get('path','/'),
            "host": params.get('host',''), "mode": params.get('mode','auto')}
    elif net == 'tcp':
        ss['tcpSettings'] = {"header": {"type": params.get('headerType','none')}}
    return ss


def make_outbound(raw_uri):
    uri = raw_uri.strip()
    def sr(s): return s.rsplit('#',1)[0] if '#' in s else s
    try:
        if uri.startswith('vless://'):
            r = sr(uri[8:]); r, par = _sp(r)
            uid, hs = r.split('@',1); h, p = _hp(hs)
            return {"protocol":"vless",
                "settings":{"vnext":[{"address":h,"port":p,
                    "users":[{"id":uid,"encryption":"none","flow":par.get('flow','')}]}]},
                "streamSettings": _stream(par)}
        if uri.startswith('vmess://'):
            j = json.loads(b64d(uri[8:]))
            par = {'type':j.get('net','tcp'),'security':j.get('tls','') or 'none',
                   'sni':j.get('sni',j.get('host','')),'path':j.get('path','/'),
                   'host':j.get('host',''),'fp':j.get('fp','chrome'),
                   'alpn':j.get('alpn',''),'headerType':j.get('type','none'),
                   'serviceName':j.get('path','')}
            return {"protocol":"vmess",
                "settings":{"vnext":[{"address":j['add'],"port":int(j['port']),
                    "users":[{"id":j['id'],"alterId":int(j.get('aid',0)),
                              "security":j.get('scy','auto')}]}]},
                "streamSettings": _stream(par)}
        if uri.startswith('trojan://'):
            r = sr(uri[9:]); r, par = _sp(r)
            pw, hs = r.split('@',1); h, p = _hp(hs)
            return {"protocol":"trojan",
                "settings":{"servers":[{"address":h,"port":p,"password":pw}]},
                "streamSettings": _stream(par)}
        if uri.startswith('ss://'):
            r = sr(uri[5:])
            if '@' in r:
                mp, hs = r.split('@',1); hs = hs.split('?')[0]
                try: mp = b64d(mp)
                except: pass
            else:
                d = b64d(r); mp, hs = d.rsplit('@',1)
            m, pw = mp.split(':',1) if ':' in mp else ('chacha20-ietf-poly1305', mp)
            h, p = _hp(hs)
            return {"protocol":"shadowsocks",
                "settings":{"servers":[{"address":h,"port":p,"method":m,"password":pw}]}}
    except: pass
    return None


def build_multi_config(servers, base_port):
    inbounds, outbounds, rules = [], [], []
    port_map = {}
    for i, srv in enumerate(servers):
        ob = make_outbound(srv['raw_uri'])
        if not ob: continue
        port = base_port + i
        sid = srv['id']
        tin, tout = f"i{sid}", f"o{sid}"
        inbounds.append({"listen":"127.0.0.1","port":port,
            "protocol":"socks","settings":{"auth":"noauth","udp":True},"tag":tin})
        ob['tag'] = tout
        outbounds.append(ob)
        rules.append({"inboundTag":[tin],"outboundTag":tout})
        port_map[sid] = port
    if not inbounds: return None, {}
    outbounds.append({"protocol":"freedom","tag":"direct"})
    return {"log":{"loglevel":"warning"},"inbounds":inbounds,
            "outbounds":outbounds,
            "routing":{"domainStrategy":"AsIs","rules":rules}}, port_map
