"""Package the independent Z7 V4 patcher as a standalone Windows executable."""

import argparse
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory

from z30_extensions.features.display_type_a_z7 import build, llvm_renderer


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "z7-firmware-extensions"
REFERENCE = ROOT / "evidence/v4-validation.json"
NAME = "Z7_FirmwarePatch_V4"


def prepare_renderer(work, source, llvm_bin):
    compile_at = llvm_renderer(llvm_bin)
    asset = work / "v4-renderer.bin"

    def record_renderer(address):
        renderer = compile_at(address)
        asset.write_bytes(struct.pack("<I", address) + renderer)
        return renderer

    eg, _ = build(source.read_bytes(), renderer_for_address=record_renderer)
    expected = json.loads(REFERENCE.read_text(encoding="utf-8"))["build"]["eg_sha256"]
    if hashlib.sha256(eg).hexdigest() != expected:
        raise ValueError("The renderer did not reproduce the V4 reference EG. Check Clang and LLD.")
    return asset


def bundle_licenses(work):
    licenses = work / "licenses"
    licenses.mkdir()
    for file in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/Wonder-Lantern.txt"):
        shutil.copyfile(PATCHER / file, licenses / Path(file).name)
    for name in ("PyInstaller", "capstone", "keystone-engine"):
        package = distribution(name)
        for file in package.files:
            if file.name.lower() in {"license.txt", "copying.txt"}:
                shutil.copyfile(package.locate_file(file), licenses / f"{name}-{file.name}")
    python = Path(sys.base_prefix)
    for name, file in (("Python-LICENSE.txt", python / "LICENSE.txt"),
                       ("Tk-license.terms", python / "tcl/tk8.6/license.terms")):
        if file.is_file():
            shutil.copyfile(file, licenses / name)
    return licenses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".private/stock/Z_7_0380.bin",
                        help="Original stock input used to verify the packaged renderer")
    parser.add_argument("--llvm-bin", type=Path, help="Directory containing reference Clang and LLD")
    parser.add_argument("--output", type=Path, default=ROOT / ".private/dist/z7-v4",
                        help="New directory for the standalone .exe")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        parser.error("Run packaging with 64-bit Python on Windows")
    output = args.output.resolve()
    if output.exists():
        parser.error("--output must be a new directory")
    local = ROOT / ".private/lab-environment.json"
    llvm_bin = args.llvm_bin
    if llvm_bin is None and local.is_file():
        configured = json.loads(local.read_text(encoding="utf-8")).get("llvm_bin")
        if configured:
            llvm_bin = Path(configured)

    private = ROOT / ".private"
    private.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="package-z7-", dir=private) as temporary:
        work = Path(temporary)
        renderer = prepare_renderer(work, args.source, llvm_bin)
        licenses = bundle_licenses(work)
        env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(work / "cache"))
        tcl = Path(sys.base_prefix) / "tcl"
        for variable, name in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
            if (tcl / name).is_dir():
                env.setdefault(variable, (tcl / name).as_posix())
        output.mkdir(parents=True)
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noupx",
            "--name", NAME, "--distpath", str(output), "--workpath", str(work / "build"),
            "--specpath", str(work), "--paths", str(PATCHER / "src"),
            "--collect-binaries", "keystone", "--collect-binaries", "capstone",
            "--add-data", f"{renderer}:.",
            "--add-data", f"{REFERENCE}:.",
            "--add-data", f"{licenses}:licenses",
            "--add-data", f"{PATCHER / 'src/z30_extensions/platform/z7_380_zero_samples.json'}:z30_extensions/platform",
            str(ROOT / "tools/windows_firmware_patch.py"),
        ], cwd=ROOT, env=env, check=True)
    print(output / f"{NAME}.exe")


if __name__ == "__main__":
    main()
