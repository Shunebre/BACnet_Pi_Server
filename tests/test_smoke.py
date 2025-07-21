import importlib.util
import argparse
import os
import unittest

from install_service import build_exec_command

class SmokeTest(unittest.TestCase):
    def test_import_and_build_exec(self):
        module_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Bacnet-server.py")
        spec = importlib.util.spec_from_file_location("bacnet_server", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = argparse.Namespace(address=None, config=None, bbmd=None, broadcast_ip=None, device_id=None)
        cmd = build_exec_command(args, module_path)
        self.assertIsInstance(cmd, str)

if __name__ == "__main__":
    unittest.main()
