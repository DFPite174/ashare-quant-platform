"""
Convenience script to start the institutional quant backend service.
Usage: python scripts/run_server.py [--port 8000] [--host 127.0.0.1]
"""
import sys
import argparse
from pathlib import Path
import uvicorn

# Ensure platform root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start A-Share Institutional Platform API")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", default=False, help="Enable auto-reload")
    args = parser.parse_args()

    print(f"[*] Starting A-Share Institutional Platform Gateway on http://{args.host}:{args.port}")
    print("[*] Engine: NautilusTrader 1.231.0 | Data: 100% Real Tushare Lake | Invariants: 10 Core Rules Active")
    uvicorn.run("backend.app:app", host=args.host, port=args.port, reload=args.reload)
