import socket
import ssl
import time
from .config import TCP_TMOUT, XRAY_TMOUT, SPEED_TMOUT, SPEED_HOST, SPEED_PATH, SPEED_PORT, SPEED_TLS, TEST_URL_HOST, TEST_URL_PATH

def tcp_ping(host, port, timeout=TCP_TMOUT):
    try:
        addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        return None, f"DNS:{e}"
    for fam, typ, pro, _, addr in addrs:
        s = socket.socket(fam, typ, pro)
        s.settimeout(timeout)
        try:
            t0 = time.monotonic()
            s.connect(addr)
            return round((time.monotonic()-t0)*1000, 1), None
        except socket.timeout: return None, "timeout"
        except OSError as e: return None, str(e)
        finally: s.close()
    return None, "no addr"

def _recvn(sock, n):
    buf = b''
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: raise ConnectionError("connection closed")
        buf += c
    return buf

def _socks5_connect(sock, host, port):
    sock.sendall(b'\x05\x01\x00')
    g = _recvn(sock, 2)
    if g != b'\x05\x00': return f"socks5 auth {g.hex()}"
    hb = host.encode() if isinstance(host, str) else host
    sock.sendall(b'\x05\x01\x00\x03' + bytes([len(hb)]) + hb + port.to_bytes(2, 'big'))
    hdr = _recvn(sock, 4)
    if hdr[1] != 0:
        codes = {1:'general',2:'denied',3:'net unreach',4:'host unreach',5:'refused',6:'TTL'}
        return codes.get(hdr[1], f"socks_err_{hdr[1]}")
    atyp = hdr[3]
    if   atyp == 1: _recvn(sock, 6)
    elif atyp == 3: _recvn(sock, _recvn(sock,1)[0] + 2)
    elif atyp == 4: _recvn(sock, 18)
    return None

def socks5_http_test(socks_port, timeout=XRAY_TMOUT):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        t0 = time.monotonic()
        s.connect(("127.0.0.1", socks_port))
        err = _socks5_connect(s, TEST_URL_HOST, 80)
        if err: return None, err
        s.sendall(f'GET {TEST_URL_PATH} HTTP/1.1\r\nHost: {TEST_URL_HOST}\r\nConnection: close\r\n\r\n'.encode())
        resp = s.recv(4096)
        ms = round((time.monotonic() - t0) * 1000, 1)
        if b'HTTP/' in resp: return ms, None
        return None, "bad http response"
    except socket.timeout: return None, "timeout"
    except Exception as e: return None, str(e)
    finally:
        try: s.close()
        except: pass

def socks5_speed_test(socks_port, host=SPEED_HOST, path=SPEED_PATH,
                      port=SPEED_PORT, use_tls=SPEED_TLS,
                      timeout=SPEED_TMOUT):
    """
    Download via SOCKS5. 15s timeout.
    Returns (size_bytes, speed_mbps, duration_s, error).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", socks_port))
        err = _socks5_connect(s, host, port)
        if err: return 0, 0, 0, err

        if use_tls:
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=host)
            s.settimeout(timeout)

        s.sendall(
            f'GET {path} HTTP/1.1\r\n'
            f'Host: {host}\r\n'
            f'Connection: close\r\n'
            f'User-Agent: vpn-monitor/4\r\n\r\n'.encode())

        hdr_buf = b''
        while b'\r\n\r\n' not in hdr_buf:
            c = s.recv(4096)
            if not c: return 0, 0, 0, "no response"
            hdr_buf += c

        hdr_part, body_start = hdr_buf.split(b'\r\n\r\n', 1)
        first_line = hdr_part.split(b'\r\n')[0]
        if b'200' not in first_line and b'206' not in first_line:
            return 0, 0, 0, f"HTTP: {first_line.decode(errors='replace')}"

        total = len(body_start)
        t0 = time.monotonic()
        while True:
            elapsed_so_far = time.monotonic() - t0
            remaining = timeout - elapsed_so_far
            if remaining <= 0: break
            s.settimeout(min(remaining, 2.0))
            try:
                chunk = s.recv(131072)
                if not chunk: break
                total += len(chunk)
            except socket.timeout: break
            except: break

        elapsed = time.monotonic() - t0
        if elapsed <= 0.001 or total <= 0: return 0, 0, 0, "no data"
        speed = (total * 8) / (elapsed * 1_000_000)
        return total, round(speed, 2), round(elapsed, 2), None

    except socket.timeout: return 0, 0, 0, "timeout"
    except Exception as e: return 0, 0, 0, str(e)
    finally:
        try: s.close()
        except: pass
