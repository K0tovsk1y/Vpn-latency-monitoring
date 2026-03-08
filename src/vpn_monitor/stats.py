import math

def calc_jitter_list(lats_ordered):
    if len(lats_ordered) < 2: return []
    return [abs(lats_ordered[i] - lats_ordered[i-1]) for i in range(1, len(lats_ordered))]

def calc_jitter(lats_ordered):
    jits = calc_jitter_list(lats_ordered)
    return sum(jits) / len(jits) if jits else 0.0

def calc_stddev(lats):
    if len(lats) < 2: return 0.0
    mean = sum(lats) / len(lats)
    return (sum((x - mean)**2 for x in lats) / (len(lats) - 1)) ** 0.5

def _pct(data, p):
    if not data: return 0
    k = (len(data)-1) * p / 100
    f = int(k); c = min(f+1, len(data)-1)
    return data[f] + (k-f)*(data[c]-data[f])

def stability_score_1(p50_ms, jitter_ms, loss_pct, p95_ms, speed_mbps=None):
    if p50_ms is None: return 0.0
    lat_f = math.exp(-p50_ms / 300.0)
    jit_f = math.exp(-jitter_ms / 100.0)
    loss_f = math.exp(-loss_pct / 20.0)
    tail_f = math.exp(-p95_ms / 600.0)
    if speed_mbps is not None and speed_mbps > 0:
        spd_f = 1.0 - math.exp(-speed_mbps / 10.0)
    else:
        spd_f = 0.0
    score = 100.0 * (lat_f**0.3) * (jit_f**0.2) * (loss_f**0.2) * (tail_f**0.15) * (spd_f**0.15)
    return round(score, 1)

def stability_score_2(mean_ms, jitter_ms, loss_pct, p95_ms, speed_mbps=None):
    if mean_ms is None: return 0.0
    lat_p = 1.0 - math.exp(-mean_ms / 300.0)
    jit_p = 1.0 - math.exp(-jitter_ms / 100.0)
    loss_p = 1.0 - math.exp(-loss_pct / 50.0)
    tail_p = 1.0 - math.exp(-p95_ms / 600.0)
    if speed_mbps is not None and speed_mbps > 0:
        spd_p = math.exp(-speed_mbps / 10.0)
    else:
        spd_p = 1.0
    penalty = (0.30 * lat_p + 0.20 * jit_p + 0.20 * loss_p + 0.15 * tail_p + 0.15 * spd_p)
    return round(max(0, (1 - penalty) * 100), 1)

def stability_score_3(p50_ms, jitter_ms, loss_pct, p95_ms, speed_mbps=None):
    if p50_ms is None: return 0.0
    lat_p = 1.0 - math.exp(-p50_ms / 300.0)
    jit_p = 1.0 - math.exp(-jitter_ms / 100.0)
    loss_p = 1.0 - math.exp(-loss_pct / 50.0)
    tail_p = 1.0 - math.exp(-p95_ms / 600.0)
    if speed_mbps is not None and speed_mbps > 0:
        spd_p = math.exp(-speed_mbps / 10.0)
    else:
        spd_p = 1.0
    penalty = (0.30 * lat_p + 0.20 * jit_p + 0.20 * loss_p + 0.15 * tail_p + 0.15 * spd_p)
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
    speed_dict = {'mean': None}
    
    if speed_rows:
        speeds = [r[0] for r in speed_rows]
        speeds_sorted = sorted(speeds)
        avg_speed = round(sum(speeds) / len(speeds), 2)
        speed_dict['mean'] = avg_speed
        for p in pcts:
            speed_dict[f'p{p}'] = round(_pct(speeds_sorted, p), 2)
    else:
        for p in pcts:
            speed_dict[f'p{p}'] = None

    def _calc(lats):
        total = len(lats)
        valid = [x for x in lats if x is not None]
        ok = len(valid)
        loss = (1 - ok/total) * 100 if total > 0 else 100.0

        jits = calc_jitter_list(valid)
        sorted_jits = sorted(jits)
        jit_mean = round(sum(jits)/len(jits), 1) if jits else 0.0
        
        if not valid:
            res = dict(n=total, loss=round(loss,1), mean=None, jit_mean=None, stddev=None, score1=0.0, score2=0.0, score3=0.0)
            for p in pcts: 
                res[f'p{p}'] = None
                res[f'jit_p{p}'] = None
            return res

        sorted_lats = sorted(valid)
        mean = sum(valid) / len(valid)
        
        res = dict(
            n=total, 
            loss=round(loss,1), 
            mean=round(mean,1), 
            jit_mean=jit_mean,
            stddev=round(calc_stddev(valid), 1)
        )
        for p in pcts:
            res[f'p{p}'] = round(_pct(sorted_lats, p), 1)
            res[f'jit_p{p}'] = round(_pct(sorted_jits, p), 1) if sorted_jits else None
            
        # Hardcode p95 extraction for score if missing from dynamic list
        p95_val = res.get('p95', _pct(sorted_lats, 95))
        p50_val = res.get('p50', _pct(sorted_lats, 50))
        res['score1'] = stability_score_1(p50_val, res['jit_mean'], loss, p95_val, avg_speed)
        res['score2'] = stability_score_2(mean, res['jit_mean'], loss, p95_val, avg_speed)
        res['score3'] = stability_score_3(p50_val, res['jit_mean'], loss, p95_val, avg_speed)
        return res

    return {
        'tcp': _calc(tcp_rows),
        'xray': _calc(xray_rows),
        'speed': speed_dict
    }
