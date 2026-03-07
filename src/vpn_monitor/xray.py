import os
import time
import json
import socket
import tempfile
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

from .config import XRAY_BIN, BASE_PORT, WORKERS
from .parsers import build_multi_config
from .tester import socks5_http_test, socks5_speed_test

def wait_port(port, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            s = socket.create_connection(("127.0.0.1", port), 0.3)
            s.close(); return True
        except: time.sleep(0.1)
    return False

class XrayManager:
    def __init__(self):
        self._proc = None
        self._tmpfile = None
        self._port_map = {}
        self._srv_ids = frozenset()
        self._lock = threading.Lock()
        self._start_count = 0

    def ensure_running(self, servers, base_port=BASE_PORT):
        new_ids = frozenset(s['id'] for s in servers)
        with self._lock:
            if self._is_alive() and new_ids == self._srv_ids:
                return dict(self._port_map)
            self._stop()
            cfg, pmap = build_multi_config(list(servers), base_port)
            if not cfg: return {}
            fd, tmp = tempfile.mkstemp(suffix='.json', prefix='xray_')
            with os.fdopen(fd, 'w') as f: json.dump(cfg, f)
            proc = subprocess.Popen([XRAY_BIN, 'run', '-c', tmp],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            time.sleep(0.6)
            if proc.poll() is not None:
                err = proc.stderr.read().decode(errors='replace')[:500]
                try: os.unlink(tmp)
                except: pass
                raise RuntimeError(f"xray crashed: {err}")
            p0 = min(pmap.values())
            if not wait_port(p0, timeout=8):
                proc.terminate(); proc.wait()
                try: os.unlink(tmp)
                except: pass
                raise RuntimeError("xray ports not ready")
            self._proc = proc
            self._tmpfile = tmp
            self._port_map = pmap
            self._srv_ids = new_ids
            self._start_count += 1
            return dict(pmap)

    def get_port(self, server_id):
        return self._port_map.get(server_id)

    def test_batch(self, servers, workers=WORKERS):
        results = {}
        for s in servers:
            if s['id'] not in self._port_map:
                results[s['id']] = (None, 'not_configured')
        testable = [s for s in servers if s['id'] in self._port_map]
        if not testable: return results
        def job(srv):
            port = self._port_map[srv['id']]
            return srv['id'], socks5_http_test(port)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(job, s): s for s in testable}
            for f in as_completed(futs):
                sid, result = f.result()
                results[sid] = result
        return results

    def speed_test_server(self, server, **kwargs):
        if server['id'] not in self._port_map:
            return 0, 0, 0, 'not_configured'
        port = self._port_map[server['id']]
        return socks5_speed_test(port, **kwargs)

    def speed_test_batch(self, servers, workers=WORKERS, **kwargs):
        results = {}
        for s in servers:
            if s['id'] not in self._port_map:
                results[s['id']] = (0, 0, 0, 'not_configured')
        testable = [s for s in servers if s['id'] in self._port_map]
        if not testable: return results
        def job(srv):
            port = self._port_map[srv['id']]
            return srv['id'], socks5_speed_test(port, **kwargs)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(job, s): s for s in testable}
            for f in as_completed(futs):
                sid, result = f.result()
                results[sid] = result
        return results

    def stop(self):
        with self._lock: self._stop()

    @property
    def starts(self): return self._start_count

    def _is_alive(self): return self._proc is not None and self._proc.poll() is None

    def _stop(self):
        if self._proc:
            self._proc.terminate()
            try: self._proc.wait(5)
            except subprocess.TimeoutExpired: self._proc.kill(); self._proc.wait()
            self._proc = None
        if self._tmpfile:
            try: os.unlink(self._tmpfile)
            except: pass
            self._tmpfile = None
        self._port_map = {}
        self._srv_ids = frozenset()

    def __del__(self): self._stop()
    def __enter__(self): return self
    def __exit__(self, *exc): self.stop()


@contextmanager
def run_xray(config):
    fd, tmp = tempfile.mkstemp(suffix='.json', prefix='xray_')
    with os.fdopen(fd, 'w') as f: json.dump(config, f)
    proc = subprocess.Popen([XRAY_BIN, 'run', '-c', tmp],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        time.sleep(0.6)
        if proc.poll() is not None:
            raise RuntimeError(f"xray crashed: {proc.stderr.read().decode()[:500]}")
        yield proc
    finally:
        proc.terminate()
        try: proc.wait(5)
        except: proc.kill(); proc.wait()
        try: os.unlink(tmp)
        except: pass


def xray_test_batch(servers, workers=WORKERS):
    cfg, pmap = build_multi_config(list(servers), BASE_PORT)
    if not cfg: return {s['id']: (None, 'unsupported') for s in servers}
    results = {}
    for s in servers:
        if s['id'] not in pmap: results[s['id']] = (None, f"unsupported:{s['protocol']}")
    testable = [s for s in servers if s['id'] in pmap]
    if not testable: return results
    try:
        with run_xray(cfg):
            p0 = min(pmap.values())
            if not wait_port(p0, timeout=8):
                for s in testable: results[s['id']] = (None, 'xray_start_fail')
                return results
            def job(srv):
                return srv['id'], socks5_http_test(pmap[srv['id']])
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {pool.submit(job, s): s for s in testable}
                for f in as_completed(futs):
                    sid, result = f.result()
                    results[sid] = result
    except FileNotFoundError:
        for s in testable: results[s['id']] = (None, f'xray not found: {XRAY_BIN}')
    except RuntimeError as e:
        for s in testable: results[s['id']] = (None, str(e))
    return results
