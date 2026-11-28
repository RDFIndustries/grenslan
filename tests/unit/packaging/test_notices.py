"""packaging/notices/notices.py: coverage checks for third-party notices, and licence copying."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
SHA = "a" * 64


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("notices", ROOT / "packaging" / "notices" / "notices.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["notices"] = module
    spec.loader.exec_module(module)
    return module


notices = _load()


def dist(
    site: Path,
    name: str,
    version: str,
    *,
    compiled: bool = False,
    licence: bool = True,
    crates: list[dict[str, object]] | None = None,
) -> Path:
    info = site / f"{name.replace('-', '_')}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n", encoding="utf-8")
    records = [f"{name}/__init__.py,,"]
    if compiled:
        records.append(f"{name}/_core.cpython-312-x86_64-linux-gnu.so,,")
    (info / "RECORD").write_text("\n".join(records) + "\n", encoding="utf-8")
    if licence:
        (info / "licenses").mkdir()
        (info / "licenses" / "LICENSE").write_text(f"{name} licence\n", encoding="utf-8")
    if crates is not None:
        (info / "sboms").mkdir()
        (info / "sboms" / "x.cyclonedx.json").write_text(json.dumps({"components": crates}), encoding="utf-8")
    return info


def crate(name: str, version: str, qualifiers: str = "") -> dict[str, object]:
    return {
        "name": name,
        "version": version,
        "purl": f"pkg:cargo/{name}@{version}{qualifiers}",
        "licenses": [{"expression": "MIT"}],
    }


def notices_dir(
    tmp: Path, lock: str, crates_txt: str | None = None, members: dict[str, list[str]] | None = None
) -> Path:
    directory = tmp / "notices"
    directory.mkdir()
    (directory / "native.lock").write_text(lock, encoding="utf-8")
    if crates_txt is not None:
        (directory / "crates.txt").write_text(crates_txt, encoding="utf-8")
    for archive, files in (members or {}).items():
        for file in files:
            (directory / "native" / archive).mkdir(parents=True, exist_ok=True)
            (directory / "native" / archive / file).write_text("text\n", encoding="utf-8")
    return directory


NATIVE = f"native  libz-1.0.tar.gz  {SHA}  https://example.org/libz-1.0.tar.gz  LICENSE  wrapz==2.0\n"


def crate_entry(name: str, version: str, used_by: str) -> str:
    return f"\n{'=' * 78}\ncrate: {name} {version}\ndeclared licence: MIT\nused by: {used_by}\n"


@pytest.fixture
def site(tmp_path: Path) -> Path:
    return tmp_path / "site"


def test_a_complete_set_of_notices_has_no_problems(tmp_path: Path, site: Path) -> None:
    dist(site, "wrapz", "2.0", compiled=True)
    dist(site, "fastthing", "1.0", compiled=True)
    dist(
        site,
        "rusty",
        "3.0",
        compiled=True,
        crates=[crate("serde", "1.0.0"), crate("rusty-core", "3.0.0", "?download_url=file://core")],
    )
    dist(site, "pure", "1.0")
    directory = notices_dir(
        tmp_path,
        NATIVE + "own-code  fastthing==1.0\n",
        crate_entry("serde", "1.0.0", "rusty==3.0"),
        {"libz-1.0.tar.gz": ["LICENSE"]},
    )
    assert notices.check([site], directory) == []


def test_compiled_code_not_listed_anywhere_is_reported(tmp_path: Path, site: Path) -> None:
    dist(site, "mystery", "1.0", compiled=True)
    assert notices.check([site], notices_dir(tmp_path, "")) == [
        "mystery==1.0: compiled code not accounted for in native.lock or an SBOM"
    ]


def test_a_version_change_of_an_embedding_wheel_is_reported(tmp_path: Path, site: Path) -> None:
    dist(site, "wrapz", "2.1", compiled=True)
    problems = notices.check([site], notices_dir(tmp_path, NATIVE, members={"libz-1.0.tar.gz": ["LICENSE"]}))
    assert "wrapz==2.1: compiled code not accounted for in native.lock or an SBOM" in problems
    assert "native.lock: libz-1.0.tar.gz names wrapz==2.0, which is not installed" in problems


def test_a_missing_native_licence_file_is_reported(tmp_path: Path, site: Path) -> None:
    dist(site, "wrapz", "2.0", compiled=True)
    assert notices.check([site], notices_dir(tmp_path, NATIVE)) == ["native/libz-1.0.tar.gz/LICENSE is missing"]


def test_crates_need_a_notice_naming_the_wheel_that_uses_them(tmp_path: Path, site: Path) -> None:
    dist(site, "rusty", "3.0", compiled=True, crates=[crate("serde", "1.0.0"), crate("log", "0.4.0")])
    problems = notices.check([site], notices_dir(tmp_path, "", crate_entry("serde", "1.0.0", "other==1.0")))
    assert "rusty==3.0: crate serde 1.0.0 has no notice" in problems
    assert "rusty==3.0: crate log 0.4.0 has no notice" in problems
    assert "crates.txt: serde 1.0.0 names other==1.0, which is not installed" in problems


def test_local_crates_are_covered_by_the_package_itself(tmp_path: Path, site: Path) -> None:
    dist(site, "rusty", "3.0", compiled=True, crates=[crate("rusty-core", "3.0.0", "?download_url=file://core")])
    assert notices.check([site], notices_dir(tmp_path, "own-code  rusty==3.0\n")) == []


def test_stale_own_code_entries_are_reported(tmp_path: Path, site: Path) -> None:
    site.mkdir()
    assert notices.check([site], notices_dir(tmp_path, "own-code  gone==1.0\n")) == [
        "native.lock: own-code gone==1.0 is not installed"
    ]


def test_packages_without_licence_files_are_reported(tmp_path: Path, site: Path) -> None:
    dist(site, "bare", "1.0", licence=False)
    assert notices.check([site], notices_dir(tmp_path, "")) == ["bare==1.0: no licence file in bare-1.0.dist-info"]
    with pytest.raises(notices.NoticeError, match=r"bare==1\.0"):
        notices.copy_python(site, tmp_path / "out")


def test_copy_python_keeps_each_packages_licence_files(tmp_path: Path, site: Path) -> None:
    info = dist(site, "Some_Package", "1.2")
    (info / "licenses" / "NOTICE").write_text("notice\n", encoding="utf-8")
    (info / "AUTHORS.rst").write_text("authors\n", encoding="utf-8")
    assert notices.copy_python(site, tmp_path / "out") == 1
    copied = sorted(p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*") if p.is_file())
    assert copied == ["some-package-1.2/licenses/LICENSE", "some-package-1.2/licenses/NOTICE"]


@pytest.mark.parametrize(
    "line",
    [
        "native  libz.tar.gz  short  https://example.org/x  LICENSE  wrapz==2.0",
        "native  libz.tar.gz  " + SHA + "  http://example.org/x  LICENSE  wrapz==2.0",
        "native  dir/libz.tar.gz  " + SHA + "  https://example.org/x  LICENSE  wrapz==2.0",
        "native  libz.tar.gz  " + SHA + "  https://example.org/x  LICENSE  wrapz",
        "own-code  thing",
        "something  else",
    ],
)
def test_malformed_lock_lines_are_refused(tmp_path: Path, line: str) -> None:
    (tmp_path / "native.lock").write_text(line + "\n", encoding="utf-8")
    with pytest.raises(notices.NoticeError):
        notices.read_lock(tmp_path / "native.lock")


def test_sbom_purls_are_classified() -> None:
    registry = notices._crate(crate("serde", "1.0.0") | {"hashes": [{"alg": "SHA-256", "content": SHA}]})
    assert (registry.kind, registry.sha256, registry.licence) == ("registry", SHA, "MIT")
    commit = "0123456789abcdef0123456789abcdef01234567"
    git = notices._crate(crate("tls", "0.1.0", f"?vcs_url=git%2Bhttps://github.com/owner/tls.git%40{commit}"))
    assert (git.kind, git.git) == ("git", ("owner", "tls", commit))
    assert notices._crate({"purl": "pkg:pypi/thing@1.0"}) is None
    with pytest.raises(notices.NoticeError, match="unsupported download_url"):
        notices._crate(crate("odd", "1.0.0", "?download_url=https://example.org/odd.crate"))
    with pytest.raises(notices.NoticeError, match="unsupported vcs_url"):
        notices._crate(crate("odd", "1.0.0", "?vcs_url=git%2Bhttps://gitlab.com/o/r%40abc"))
