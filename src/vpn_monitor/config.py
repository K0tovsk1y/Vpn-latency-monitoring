import os, sys

DB_FILE    = "vpn_latency.db"
TCP_TMOUT  = 5
XRAY_TMOUT = 15
SPEED_TMOUT = 15
XRAY_BIN   = os.environ.get("XRAY_PATH", "xray")
WORKERS    = 8
BASE_PORT  = 31000

TEST_URL_HOST = "www.gstatic.com"
TEST_URL_PATH = "/generate_204"

# Speed test defaults — Cloudflare HTTPS
SPEED_HOST  = "speed.cloudflare.com"
SPEED_PATH  = "/__down?bytes=5242880"
SPEED_PORT  = 443
SPEED_TLS   = True

_TTY = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

class C:
    RST  = '\033[0m'  if _TTY else ''
    RED  = '\033[91m' if _TTY else ''
    GRN  = '\033[92m' if _TTY else ''
    YEL  = '\033[93m' if _TTY else ''
    BLU  = '\033[94m' if _TTY else ''
    CYN  = '\033[96m' if _TTY else ''
    DIM  = '\033[2m'  if _TTY else ''
    BLD  = '\033[1m'  if _TTY else ''

    @staticmethod
    def lat(ms):
        if ms is None: return C.RED
        if ms < 100:   return C.GRN
        if ms < 200:   return C.CYN
        if ms < 400:   return C.YEL
        return C.RED

    @staticmethod
    def spd(mbps):
        if mbps is None or mbps <= 0: return C.RED
        if mbps >= 10:  return C.GRN
        if mbps >= 3:   return C.CYN
        if mbps >= 1:   return C.YEL
        return C.RED

    @staticmethod
    def score(s):
        if s is None: return C.DIM
        if s >= 80:   return C.GRN
        if s >= 60:   return C.CYN
        if s >= 40:   return C.YEL
        return C.RED
