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
    parser.add_argument("--iso-double-click", action="store_true",
                        help="Add the body ISO shortcut with its saved f8 On/Off setting")
    parser.add_argument("--af-on-af-c", action="store_true",
                        help="Build the f8 ISO shortcut together with the f9 AF-ON shortcut")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")
    try:
        eg, report = build(args.source.read_bytes(), args.llvm_bin,
                           iso_double_click=args.iso_double_click, af_on_af_c=args.af_on_af_c)
    except (OSError, ValueError, CalledProcessError) as error:
        parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "display.emulator.eg.bin").write_bytes(eg)
    (args.output / "display.emulator.main.bin").write_bytes(eg[:-2])
    (args.output / "display.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EG SHA-256 {report['sha256']}")


if __name__ == "__main__":
    main()
