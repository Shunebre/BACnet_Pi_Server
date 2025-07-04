#!/usr/bin/env python3
"""Install and manage the bacnet.service unit."""

import argparse
import os
import subprocess
import sys

SERVICE_PATH = "/etc/systemd/system/bacnet.service"


def build_exec_command(args, server_path):
    cmd = [sys.executable, server_path]
    if args.address:
        cmd += ["--address", args.address]
    if args.config:
        cmd += ["--config", args.config]
    if args.bbmd:
        cmd += ["--bbmd", args.bbmd]
    if args.broadcast_ip:
        cmd += ["--broadcast-ip", args.broadcast_ip]
    if args.device_id is not None:
        cmd += ["--device-id", str(args.device_id)]
    return " ".join(cmd)


def write_service_file(path, working_dir, exec_cmd):
    content = f"""[Unit]
Description=BACnet server for Raspberry Pi
After=network.target

[Service]
Type=simple
WorkingDirectory={working_dir}
ExecStart={exec_cmd}
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""
    with open(path, "w") as srv:
        srv.write(content)


def run_systemctl(commands):
    for cmd in commands:
        subprocess.run(["systemctl"] + cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Install BACnet Pi Server as a systemd service")
    parser.add_argument("--address", help="BIP address ip/prefix:port")
    parser.add_argument("--config", default="objects.json", help="Additional objects file")
    parser.add_argument("--bbmd", help="BBMD address")
    parser.add_argument("--broadcast-ip", help="Custom broadcast address")
    parser.add_argument("--device-id", type=int, help="BACnet device id")
    parser.add_argument("--service-path", default=SERVICE_PATH, help="Service file path")
    args = parser.parse_args()

    cwd = os.path.abspath(os.path.dirname(__file__))
    server_path = os.path.join(cwd, "Bacnet-server.py")
    exec_cmd = build_exec_command(args, server_path)

    try:
        write_service_file(args.service_path, cwd, exec_cmd)
    except PermissionError:
        print(f"Permesso negato: {args.service_path}")
        sys.exit(1)

    try:
        run_systemctl([["daemon-reload"], ["enable", os.path.basename(args.service_path)], ["restart", os.path.basename(args.service_path)]])
    except subprocess.CalledProcessError:
        print("BACnet_Pi_Server fallito avviamento")
        sys.exit(1)

    print("BACnet_Pi_Server avviato con successo")


if __name__ == "__main__":
    main()
