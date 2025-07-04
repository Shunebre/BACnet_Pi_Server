# BACnet Pi Server

This project provides a simple BACnet server for Raspberry Pi exposing GPIO pins as BACnet points.

The server configures the `protocolObjectTypesSupported` property based on the BACpypes library and maps even BCM pins (2–27) as *Binary Inputs* while odd pins are *Binary Outputs*. Each object is named `GPIOX` and uses the pin number as description. For output objects the `polarity` property can be set to `normal` or `reverse`.

## Adding dynamic objects

Additional objects can be declared in an `objects.json` file located next to the script. Each entry must specify the Python module, class and parameters to pass when instantiating the object. The file bundled in this repository shows an example of `BinaryInputObject` and `AnalogValueObject`.

## Usage

Install the dependencies with:

```bash
pip install -r requirements.txt
```

Run the server with:

```bash
./Bacnet-server.py
```

Optional arguments:

- `--bbmd` register to a BBMD (useful when working through a VPN)
- `--broadcast-ip` set a custom broadcast address
- `--device-id` change the BACnet device ID

### systemd service example

An example unit file can be found in the `systemd/` directory as `bacnet.service`. Adjust the `WorkingDirectory` and `ExecStart` paths then enable the service with:

```bash
sudo systemctl enable bacnet.service
```

### Automatic systemd setup

The `install_service.py` helper creates and starts the service with your
parameters, automatically reloading the daemon and enabling the unit. For
example:

```bash
sudo python3 install_service.py --address 192.168.1.10/24:47808 --device-id 123
```

On success the script prints `BACnet_Pi_Server avviato con successo`. If the
startup fails `BACnet_Pi_Server fallito avviamento` is shown.

### Versioning

The current version is stored in the `VERSION` file. Each code change should bump the version by **0.0.1** so that the `applicationSoftwareVersion` and `firmwareRevision` properties remain aligned.

