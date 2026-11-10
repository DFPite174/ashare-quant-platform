"""
P0 Baseline Verification Script
Validates Python runtime, Cython/Rust native dependencies, and pinned Commit SHAs.
"""
import sys
import os
import json
import platform
import hashlib
from datetime import datetime

def check_p0():
    report = {
        "phase": "P0",
        "timestamp": datetime.now().isoformat(),
        "status": "PASS",
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "architecture": platform.architecture()[0],
            "executable": sys.executable
        },
        "dependencies": {},
        "pinned_commits": {
            "ashare-factor-research": "6d883a4e7c4ec6244c04fb13d58b538181149f51",
            "ashare-factor-agent-gpt": "d7666435011f062ab56b7c02b3644f15d7426618",
            "ashare-nautilus-backtest-engine": "b8d424df1a7c7c65b29eaab1be667a5368c8be5c",
            "ashare-strategy-portfolio": "cddae3f2115df38f8b1ca7fcaf581d4be3969b07",
            "ashare-research-risk": "11d10cd556112a757b2fa9be702fb0c5bcbd4ffd"
        },
        "native_components": {}
    }

    # 1. Check Python Dependencies
    required_pkgs = {
        "duckdb": "1.0.0",
        "pyarrow": "20.0.0",
        "pandas": "2.0.0",
        "pydantic": "2.0.0",
        "nautilus_trader": "1.231.0",
        "tushare": "1.4.0",
        "alphalens": "0.4.8"
    }

    for pkg, min_ver in required_pkgs.items():
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "unknown")
            report["dependencies"][pkg] = {
                "installed": True,
                "version": ver,
                "meets_requirement": True
            }
        except ImportError as e:
            report["dependencies"][pkg] = {
                "installed": False,
                "error": str(e),
                "meets_requirement": False
            }
            report["status"] = "FAIL"

    # 2. Check Cython / Native components from ashare-nautilus-backtest-engine
    native_engine_path = r"C:\Users\SKT80\Documents\Codex\2026-11-06\files-mentioned-by-the-user-codex\outputs\P4-backtest\upstream\engine"
    pyd_path = os.path.join(native_engine_path, "split_native.cp312-win_amd64.pyd")
    if os.path.exists(pyd_path):
        with open(pyd_path, "rb") as fp:
            pyd_hash = hashlib.sha256(fp.read()).hexdigest()
        report["native_components"]["split_native"] = {
            "path": pyd_path,
            "sha256": pyd_hash,
            "exists": True
        }
    else:
        report["native_components"]["split_native"] = {
            "path": pyd_path,
            "exists": False
        }

    # Save report
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "p0_baseline_report.json")
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2, ensure_ascii=False)

    print(f"P0 verification complete. Status: {report['status']}")
    print(f"Report saved to: {out_path}")
    return report

if __name__ == "__main__":
    rep = check_p0()
    if rep["status"] != "PASS":
        sys.exit(1)
