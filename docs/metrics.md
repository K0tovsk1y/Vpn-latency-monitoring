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

### Formula Weights
The score starts at 100 and applies "penalty points" based on the following components:

| Component | Max Penalty | Calculation |
| :--- | :--- | :--- |
| **Average Latency** | 30% | Linear penalty up to 500ms. |
| **Jitter** | 20% | Linear penalty up to 200ms. |
| **Packet Loss** | 20% | Direct percentage penalty (100% loss = 20 points). |
| **Tail Latency (P95)**| 15% | Linear penalty up to 1000ms. |
| **Speed (Optional)** | 15% | Penalty for low speed (0 Mbps = 15 points, 20+ Mbps = 0 points). |

**Simplified Logic**:
`Score = MAX(0, (1 - Σ (Metric / Threshold * Weight)) * 100)`

> [!TIP]
> This formula is intentionally "aggressive". A server with 10% packet loss will rarely score above 60, even if its latency is very low.

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
