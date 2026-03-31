from pathlib import Path

from chat_attachments import ALLOWED_EXTENSIONS, _extract_one_file


def test_cad_extensions_are_allowed() -> None:
    assert "dxf" in ALLOWED_EXTENSIONS
    assert "dwg" in ALLOWED_EXTENSIONS


def test_dxf_summary_extracts_basic_counts(tmp_path: Path) -> None:
    dxf = tmp_path / "sample.dxf"
    dxf.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "TABLES",
                "0",
                "LAYER",
                "2",
                "Layer_A",
                "0",
                "LAYER",
                "2",
                "Layer_B",
                "0",
                "ENDSEC",
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "LINE",
                "0",
                "CIRCLE",
                "0",
                "LINE",
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        ),
        encoding="utf-8",
    )
    out = _extract_one_file(dxf, "sample.dxf", "dxf")
    assert "DXF 摘要" in out
    assert "图层数：2" in out
    assert "实体总数：3" in out
    assert "LINE:2" in out


def test_dwg_summary_returns_capability_hint(tmp_path: Path) -> None:
    dwg = tmp_path / "sample.dwg"
    dwg.write_bytes(b"AC1027\x00DWGDATA")
    out = _extract_one_file(dwg, "sample.dwg", "dwg")
    assert "DWG 文件" in out
    assert "建议另存为 DXF" in out
