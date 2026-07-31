# -*- coding: utf-8 -*-

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.md2img import _markdown_to_image_m2f, _markdown_to_image_wkhtml


def test_wkhtml_renderer_uses_share_poster_dimensions_and_qr_template():
    with patch("imgkit.from_string", return_value=b"png") as render:
        assert _markdown_to_image_wkhtml("# 大盘复盘\n\n## 结论\n\n震荡") == b"png"

    html, output = render.call_args.args
    options = render.call_args.kwargs["options"]
    assert output is False
    assert 'class="poster market"' in html
    assert "项目主页二维码" in html
    assert "小红书二维码" in html
    assert options["width"] == 1080
    assert options["disable-smart-width"] == ""


def test_markdown_to_file_renderer_receives_the_same_share_poster(tmp_path, monkeypatch):
    captured = {}

    def fake_run(args, **_kwargs):
        captured["html"] = Path(args[1]).read_text(encoding="utf-8")
        (tmp_path / "report.png").write_bytes(b"png")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr("src.md2img.shutil.which", lambda _name: "m2f")
    monkeypatch.setattr("src.md2img.tempfile.mkdtemp", lambda: str(tmp_path))
    monkeypatch.setattr("src.md2img.subprocess.run", fake_run)
    monkeypatch.setattr("src.md2img.shutil.rmtree", lambda _path: None)

    assert _markdown_to_image_m2f("# 贵州茅台 600519\n\n## 结论\n\n偏多") == b"png"
    assert 'class="poster stock"' in captured["html"]
    assert "项目主页二维码" in captured["html"]
    assert "小红书二维码" in captured["html"]
