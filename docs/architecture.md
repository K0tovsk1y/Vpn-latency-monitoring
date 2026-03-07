# Architecture & Internals

This project is built with a focus on modularity, reliability, and accuracy in proxy measurements. It carefully isolates proxy processes and manages concurrent tests to ensure that results are not tainted by system state or environmental noise.

---

## 📁 File Structure & Core Responsibilities

- **`run.py`**: The thin entry point. Its only job is to set up the Python path and delegate to the `main` module.
- **`src/vpn_monitor/main.py`**: Handles CLI argument parsing using `argparse`. It defines the interface for all user commands.
- **`src/vpn_monitor/commands.py`**: The "orchestrator". Contains the top-level logic for high-level operations like `fetch`, `monitor`, and `stats`.
- **`src/vpn_monitor/xray.py`**: Manages the lifecycle of `xray-core` subprocesses. Includes config generation and port synchronization.
- **`src/vpn_monitor/tester.py`**: Contains the protocol-level implementation for TCP pings, SOCKS5 handshakes, and bandwidth testing.
- **`src/vpn_monitor/stats.py`**: The "mathematics engine". Implements jitter, score calculation, and database aggregation.
- **`src/vpn_monitor/parsers.py`**: Utilities for parsing complex VPN URIs (VLESS, VMESS, etc.) and generating the JSON configurations required by Xray.
- **`src/vpn_monitor/config.py`**: Centralized configuration store (environment variables and defaults).
- **`src/vpn_monitor/db.py`**: SQLite schema definition and connection pool management.

---

## 🛰️ Xray Lifecycle Management

The key to accurate monitoring in this tool is the **"Clean Instance"** approach. We do not use a global proxy; instead, we spin up isolated `xray` processes.

### 1. Port Allocation
When testing a batch of servers, the tool:
- Starts from `BASE_PORT` (default: `31000`).
- Iterates to find available local TCP ports.
- Maps each server ID to a specific local SOCKS5 port.

### 2. Configuration Generation
For every measurement, we generate a temporary JSON configuration:
- **Inbound**: A standard SOCKS5 proxy listening on the allocated local port.
- **Outbound**: The specific VPN server configuration parsed from the subscription.
- **Routing**: Strict rules ensuring that traffic from a specific inbound port *always* exits through the corresponding outbound proxy.

### 3. Cleanup
Once measurements are finished (or if the tool crashes/is interrupted), all spawned `xray` processes are gracefully terminated, and their temporary configuration files are removed.

---

## 🧵 Threading & Parallelism

To handle large subscriptions (100+ nodes), we utilize `ThreadPoolExecutor` in two main areas:

- **TCP Pinging**: Highly parallelized. Since TCP pings are almost entirely network-bound and have low CPU overhead, we can run dozens in parallel.
- **Xray Testing**: Balanced parallelization. Running too many `xray` instances simultaneously can lead to CPU spikes and inaccurate latency. We default to **8 workers** to maintain a balance between speed and accuracy.

---

## 💾 Database Schema

The SQLite database (`vpn_latency.db`) is structured for rapid insertion and flexible aggregation.

### Table: `servers`
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key (Major ID). |
| `sub_url` | TEXT | Source subscription link. |
| `protocol` | TEXT | vless, vmess, trojan, etc. |
| `transport` | TEXT | tcp, ws, grpc, etc. |
| `host`/`port` | TEXT/INT | Destination server address. |
| `remark` | TEXT | User-facing server name. |
| `uri_key` | TEXT | UNIQUE hash used to prevent duplicates. |

### Table: `pings`
| Field | Type | Description |
| :--- | :--- | :--- |
| `server_id` | INTEGER | Foreign Key to `servers.id`. |
| `method` | TEXT | 'tcp' or 'xray'. |
| `latency_ms`| REAL | Round-trip time (NULL on failure). |
| `ts` | TEXT | Normalized timestamp: `YYYY-MM-DD HH:MM:SS`. |
| `error` | TEXT | Human-readable error message. |

### Table: `speed_tests`
| Field | Type | Description |
| :--- | :--- | :--- |
| `server_id` | INTEGER | Foreign Key to `servers.id`. |
| `speed_mbps`| REAL | Megabits per second. |
| `ts` | TEXT | Normalized timestamp. |
