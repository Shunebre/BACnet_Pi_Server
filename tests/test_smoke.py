import argparse
import importlib.util
from pathlib import Path
import sys

# Use stub RPi.GPIO from tests/stubs
sys.path.insert(0, str(Path(__file__).parent / "stubs"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import Bacnet-server.py as a module
server_path = Path(__file__).resolve().parents[1] / "Bacnet-server.py"
spec = importlib.util.spec_from_file_location("bacnet_server", server_path)
bacnet_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bacnet_server)

from install_service import build_exec_command


def test_build_exec_command():
    args = argparse.Namespace(
        address="1.2.3.4/24:47808",
        config=None,
        bbmd=None,
        broadcast_ip=None,
        device_id=1,
    )
    cmd = build_exec_command(args, str(server_path))
    assert str(server_path) in cmd

