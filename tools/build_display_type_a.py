"""Build the Type A display experiment from a locally supplied Z7 update file."""

import argparse
import json
from pathlib import Path
from subprocess import CalledProcessError
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "z7-firmware-extensions/src"))
from z30_extensions.features.display_type_a_z7 import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New directory for the private EG, MAIN and manifest")
    parser.add_argument("--llvm-bin", type=Path, help="Directory containing clang and ld.lld")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")
    try:
        eg, report = build(args.source.read_bytes(), args.llvm_bin)
    except (OSError, ValueError, CalledProcessError) as error:
        parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "display.emulator.eg.bin").write_bytes(eg)
    (args.output / "display.emulator.main.bin").write_bytes(eg[:-2])
    (args.output / "display.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EG SHA-256 {report['sha256']}")


if __name__ == "__main__":
    main()
