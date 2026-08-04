"""Run the full pipeline in order."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
scripts = [
    "scripts/clean_data.py",
    "scripts/build_kpis.py",
    "scripts/detect_drift.py",
    "scripts/explain_causes.py",
    "notebooks/eda.py",
]

for s in scripts:
    print(f"\n>>> Running {s}")
    result = subprocess.run([sys.executable, str(ROOT / s)], cwd=ROOT)
    if result.returncode != 0:
        print(f"FAILED: {s}")
        sys.exit(1)
print("\nDone. Check results/ and exports/")
print("Open exports/ for Excel, CSVs and charts")
