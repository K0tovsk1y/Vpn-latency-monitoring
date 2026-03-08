# Metrics & Scoring

The VPN Monitor tool uses a set of mathematical metrics to evaluate connection quality, stability, and performance.

---

## 🛰️ Connectivity Metrics

### Latency (ms)
The time it takes for a packet to travel from the local machine to the target and back.
- **TCP Ping**: Measured at the transport layer (L4). Fast but does not verify proxy functionality.
- **Xray Ping**: Measured through a SOCKS5 tunnel (L7). It performs a full **HTTP/1.1 GET request** to a target host (default: `www.gstatic.com/generate_204`). It verifies that the proxy core is running, authenticated, and capable of routing real web traffic. This is a "real-world" latency measure, significantly higher than a raw TCP handshake.

### Jitter (ms)
Jitter represents the variation in latency over time. We calculate it as the **Average Absolute Difference** between consecutive pings:
> `Jitter = Σ |Latency[i] - Latency[i-1]| / (N - 1)`
> *Where N is the number of successful pings.*

High jitter results in "stuttering" during real-time applications like voice calls or gaming.

### Packet Loss (OK%)
Percentage of successful probes vs. total attempts.
- **`OK%`** in the `stats` table is simply `100 - Loss%`.
- Any probe that times out or returns a protocol error is counted as a failure.

---

## 🏆 Stability Score (0 - 100)

The **Stability Score** is a weighted algorithm designed to penalize instability and reward consistent high performance. It converts various metrics into a single "Health Index".

We offer 3 different scoring formulas, all of which are strictly monotonic and continuous. By default, **`Score2`** is used for `--sort score`:
- **`score1` (Multiplicative Exponential):** 
  `Score = 100 * (lat_f^0.30) * (jit_f^0.20) * (loss_f^0.20) * (tail_f^0.15) * (spd_f^0.15)`
  *Extremely aggressive. A single bad metric zeroes out the total score.*
- **`score2` (Additive Exponential) [DEFAULT]:**
  `Score = MAX(0, 100 * (1 - (0.30*lat_p + 0.20*jit_p + 0.20*loss_p + 0.15*tail_p + 0.15*spd_p)))`
  Uses normalized exponentially decaying penalty values like `lat_p = 1 - exp(-latency/300)`. It computes a weighted sum of penalties, ensuring it converges smoothly and strictly to 0 without capping abruptly. 
- **`score3` (Fractional):**
  `Score = MAX(0, 100 * (1 - (0.30*lat_p + 0.20*jit_p + 0.20*loss_p + 0.15*tail_p + 0.15*spd_p)))`
  Uses rational fractions for penalties like `lat_p = mean / (mean + 150)`. It penalizes slower, creating longer "tails" where bad and very bad servers can still be differentiated slightly.

> [!TIP]
> This new exponential/fractional curve applies a stricter penalty at the median ranges, but never abruptly "caps out". Any small improvement will mathematically improve the score.

---

## 📊 Statistical Distribution

### Percentiles (P50, P90, P95)
Percentiles help identify "spikes" that simple averages might hide:
- **P50 (Median)**: The "typical" experience.
- **P90**: 90% of your traffic is faster than this.
- **P95**: The "worst-case" scenario for most users. If P95 is much higher than P50, it indicates an unstable line with frequent lag spikes.

### Standard Deviation (σ)
Measures the "spread" of latency values. A high σ (sigma) means the connection performance is highly unpredictable.

---

## 🚀 Speed Testing
The speed test downloads a specific chunk of data (default: **5MB**) from a fast CDN (default: **Cloudflare**).
- **Mbps**: We measure the time from the first byte to the last byte.
- **Formula**: `(Total Bytes * 8) / (Elapsed Seconds * 1,000,000)`
- Tests are performed sequentially in `test` mode or as part of a scheduled round in `monitor` mode.
