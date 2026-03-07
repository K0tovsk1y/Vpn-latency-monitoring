from .config import C
from .utils import _srv_name

def _show(srv, lat, err, prev_lat=None):
    name = _srv_name(srv)
    tr = (srv['transport'] or 'tcp')[:6]
    if lat is not None:
        col = C.lat(lat)
        bar = '█' * min(int(lat / 15), 40)
        delta = ''
        if prev_lat is not None and prev_lat > 0:
            d = lat - prev_lat
            pct = d / prev_lat * 100
            delta = f" ({pct:+.0f}%)"
        jit_str = ''
        if prev_lat is not None:
            j = abs(lat - prev_lat)
            jit_str = f" Δ{j:.0f}"
        print(f"  {name:38s} [{tr:6s}] "
              f"{col}{lat:7.1f} ms{C.RST}{delta}{jit_str}  "
              f"{C.DIM}{bar}{C.RST}")
    else:
        print(f"  {name:38s} [{tr:6s}] "
              f"{C.RED}   FAIL{C.RST}     ({err})")


def _show_monitor_line(srv, lat, err, prev_lat, method='XRAY'):
    name = _srv_name(srv, 30)
    tr = (srv['transport'] or 'tcp')[:6]
    if lat is not None:
        col = C.lat(lat)
        jit = ''
        if prev_lat is not None:
            jit = f"  Δ{abs(lat - prev_lat):.0f}"
        print(f"         {name:30s} [{tr:4s}] {col}{lat:7.1f} ms{C.RST}{jit}")
    else:
        print(f"         {name:30s} [{tr:4s}] {C.RED}   FAIL{C.RST} ({err})")


def _show_speed_line(srv, sz, speed, dur, err):
    name = _srv_name(srv, 30)
    if err:
        print(f"         {name:30s} {C.RED}FAIL{C.RST} ({err})")
    else:
        col = C.spd(speed)
        print(f"         {name:30s} {col}{speed:6.2f} Mbps{C.RST} "
              f"({sz/1_000_000:.1f}MB/{dur:.1f}s)")
