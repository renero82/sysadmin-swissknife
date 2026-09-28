import shutil
import subprocess

import pytest

from sysadmin_swissknife.motd import FONTS, FRAMES, ICONS, LEGAL_EN, MotdConfig, build

BASH = shutil.which("bash")


def text(res):
    return ["".join(t for t, _ in line) for line in res.preview]


def test_all_fonts_exist_and_render():
    for f in FONTS:
        res = build(MotdConfig(banner="ab", font=f, info=[]))
        assert not res.warnings and res.preview, f


def test_static_plain():
    res = build(MotdConfig(banner="web01", banner_color="none", message="hello",
                           message_color="none", info=[]))
    assert "\x1b" not in res.content and "hello" in res.content
    assert res.filename == "motd"


def test_static_colors_and_info_warning():
    res = build(MotdConfig(banner="web01", info=["hostname"]))
    assert "\x1b[1;36m" in res.content
    assert any("dynamic script" in w for w in res.warnings)


@pytest.mark.parametrize("frame", [f for f in FRAMES if f != "none"])
def test_frames_are_rectangular(frame):
    res = build(MotdConfig(banner="db01", frame=frame, icon="server", message=LEGAL_EN,
                           target="debian", center=True))
    widths = {len(l) for l in text(res)}
    assert len(widths) == 1, widths


@pytest.mark.skipif(not BASH, reason="bash not available")
@pytest.mark.parametrize("target", ["debian", "rhel"])
@pytest.mark.parametrize("frame", ["none", "double"])
def test_scripts_are_valid_and_run(tmp_path, target, frame):
    cfg = MotdConfig(banner="it's $HOME `x` 100%", font="small", frame=frame, icon="cloud",
                     message="don't panic \\ 50%", target=target,
                     info=["hostname", "os", "kernel", "load", "memory", "disk", "users", "date"])
    res = build(cfg)
    f = tmp_path / res.filename
    f.write_text(res.content)
    subprocess.run([BASH, "-n", str(f)], check=True)
    if target == "debian":
        out = subprocess.run([BASH, str(f)], capture_output=True, text=True, check=True).stdout
    else:
        out = subprocess.run([BASH, "-ic", f"source {f}"], capture_output=True, text=True,
                             check=True).stdout
        # non-interactive shells must stay silent (scp, cron, scripts...)
        quiet = subprocess.run([BASH, "-c", f"source {f}"], capture_output=True, text=True)
        assert quiet.stdout == "" and quiet.returncode == 0
    assert "Hostname:" in out and "don't panic \\ 50%" in out
    if frame == "double":
        plain = [l for l in out.replace("\x1b[0m", "").splitlines()]
        import re
        plain = [re.sub(r"\x1b\[[0-9;]*m", "", l) for l in plain]
        assert len({len(l) for l in plain if l}) == 1   # frame stays aligned with real values
        assert len([l for l in plain if l]) == len(res.preview)   # top and bottom border included
