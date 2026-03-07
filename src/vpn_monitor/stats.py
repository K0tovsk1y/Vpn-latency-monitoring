def calc_jitter(lats_ordered):
    if len(lats_ordered) < 2: return 0.0
    diffs = [abs(lats_ordered[i] - lats_ordered[i-1]) for i in range(1, len(lats_ordered))]
    return sum(diffs) / len(diffs)

def calc_stddev(lats):
    if len(lats) < 2: return 0.0
    mean = sum(lats) / len(lats)
    return (sum((x - mean)**2 for x in lats) / (len(lats) - 1)) ** 0.5

def _pct(data, p):
    if not data: return 0
    k = (len(data)-1) * p / 100
    f = int(k); c = min(f+1, len(data)-1)
    return data[f] + (k-f)*(data[c]-data[f])

def stability_score(mean_ms, jitter_ms, loss_pct, p95_ms, speed_mbps=None):
    if mean_ms is None: return 0.0

    lat_p  = min(mean_ms / 500, 1.0)
    jit_p  = min(jitter_ms / 200, 1.0)
    loss_p = min(loss_pct / 100, 1.0)
    tail_p = min(p95_ms / 1000, 1.0)

    # Speed: 0 Mbps = penalty 1.0, 20+ Mbps = penalty 0.0
    if speed_mbps is not None and speed_mbps > 0:
        spd_p = max(0, 1.0 - speed_mbps / 20)
    else:
        spd_p = 1.0  # no data = maximum penalty

    penalty = (0.30 * lat_p +
               0.20 * jit_p +
               0.20 * loss_p +
               0.15 * tail_p +
               0.15 * spd_p)
    return round(max(0, (1 - penalty) * 100), 1)

def gather_server_stats(conn, server_id, since, until=None, pcts=None):
    if pcts is None: pcts = [50, 90, 95]
    
    if until:
        pings = conn.execute(
            "SELECT method, latency_ms FROM pings WHERE server_id=? AND ts>=? AND ts<=? ORDER BY ts ASC", 
            (server_id, since, until)).fetchall()
        speed_rows = conn.execute(
            "SELECT speed_mbps FROM speed_tests "
            "WHERE server_id=? AND ts>=? AND ts<=? AND speed_mbps>0 "
            "ORDER BY ts DESC",
            (server_id, since, until)).fetchall()
    else:
        pings = conn.execute(
            "SELECT method, latency_ms FROM pings WHERE server_id=? AND ts>=? ORDER BY ts ASC", 
            (server_id, since)).fetchall()
        speed_rows = conn.execute(
            "SELECT speed_mbps FROM speed_tests "
            "WHERE server_id=? AND ts>=? AND speed_mbps>0 "
            "ORDER BY ts DESC",
            (server_id, since)).fetchall()
    
    tcp_rows = [r[1] for r in pings if r[0] == 'tcp']
    xray_rows = [r[1] for r in pings if r[0] == 'xray']
    
    avg_speed = None
    if speed_rows:
        speeds = [r[0] for r in speed_rows]
        avg_speed = round(sum(speeds) / len(speeds), 2)

    def _calc(lats):
        total = len(lats)
        valid = [x for x in lats if x is not None]
        ok = len(valid)
        loss = (1 - ok/total) * 100 if total > 0 else 100.0

        if not valid:
            res = dict(n=total, loss=round(loss,1), mean=None, jit_mean=None, stddev=None, score=0.0)
            for p in pcts: res[f'p{p}'] = None
            return res

        sorted_lats = sorted(valid)
        mean = sum(valid) / len(valid)
        
        res = dict(
            n=total, 
            loss=round(loss,1), 
            mean=round(mean,1), 
            jit_mean=round(calc_jitter(valid), 1),
            stddev=round(calc_stddev(valid), 1)
        )
        for p in pcts:
            res[f'p{p}'] = round(_pct(sorted_lats, p), 1)
            
        # Hardcode p95 extraction for score if missing from dynamic list
        p95_val = res.get('p95', _pct(sorted_lats, 95))
        res['score'] = stability_score(mean, res['jit_mean'], loss, p95_val, avg_speed)
        return res

    return {
        'tcp': _calc(tcp_rows),
        'xray': _calc(xray_rows),
        'speed': {'mean': avg_speed}
    }
