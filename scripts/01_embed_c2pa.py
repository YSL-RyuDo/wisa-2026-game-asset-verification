import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS_CSV = ROOT / "metadata" / "assets.csv"
ORIGINAL_DIR = ROOT / "data" / "original"
SIGNED_DIR = ROOT / "data" / "signed"
MANIFEST_DIR = ROOT / "manifests" / "generated"
LOG_DIR = ROOT / "results" / "c2pa_logs"

CLAIM_GENERATOR = "wisa2026-c2pa-game-assets/0.1"

def make_manifest(row: dict) -> dict:
    title = row["asset_id"]
    asset_type = row["asset_type"]
    return {
        "claim_generator": CLAIM_GENERATOR,
        "title": title,
        "assertions": [
            {
                "label": "stds.schema-org.CreativeWork",
                "data": {
                    "@context": "https://schema.org",
                    "@type": "CreativeWork",
                    "name": title,
                    "description": f"Generated {asset_type} game image asset for C2PA preservation and perceptual hash re-identification experiment.",
                    "creator": [
                        {
                            "@type": "Organization",
                            "name": "Anonymous Research Dataset"
                        }
                    ],
                    "genre": "game image asset",
                    "encodingFormat": "image/png"
                }
            },
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            "softwareAgent": "anything-v5.safetensors",
                            "parameters": {
                                "asset_id": row["asset_id"],
                                "asset_type": asset_type,
                                "source": row.get("source", "generated"),
                                "description": row.get("description", "")
                            }
                        }
                    ]
                }
            }
        ]
    }

def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, shell=False)

def main():
    SIGNED_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with ASSETS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    ok, fail = 0, 0

    for row in rows:
        src = ROOT / row["relative_path"]
        out_dir = SIGNED_DIR / row["asset_type"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / row["file_name"]

        manifest_path = MANIFEST_DIR / f"{row['asset_id']}.json"
        manifest_path.write_text(json.dumps(make_manifest(row), ensure_ascii=False, indent=2), encoding="utf-8")

        if not src.exists():
            fail += 1
            (LOG_DIR / f"{row['asset_id']}_sign_error.txt").write_text(f"Missing source file: {src}\n", encoding="utf-8")
            print(f"[MISSING] {src}")
            continue

        cmd = [
            "c2patool",
            str(src),
            "-m",
            str(manifest_path),
            "-o",
            str(out),
            "-f",
        ]
        result = run(cmd)

        log_text = (
            f"COMMAND: {' '.join(cmd)}\n\n"
            f"RETURN_CODE: {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}\n"
        )
        (LOG_DIR / f"{row['asset_id']}_sign.txt").write_text(log_text, encoding="utf-8")

        if result.returncode == 0 and out.exists():
            ok += 1
            print(f"[SIGNED] {row['asset_id']} -> {out}")
        else:
            fail += 1
            print(f"[FAILED] {row['asset_id']}")

    print(f"\nDone. signed={ok}, failed={fail}")

if __name__ == "__main__":
    main()
