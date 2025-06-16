import logging
import json
import importlib
import argparse
from ipaddress import ip_interface
import RPi.GPIO as GPIO


from bacpypes.core import run, stop
from bacpypes.app import BIPSimpleApplication
from bacpypes.object import (
    BinaryInputObject,
    BinaryOutputObject,
)
from bacpypes.local.device import LocalDeviceObject
from bacpypes.task import RecurringTask
from bacpypes.primitivedata import Unsigned
from bacpypes.basetypes import StatusFlags, Polarity
from bacpypes.primitivedata import ObjectType
from bacpypes.pdu import Address

# Versione del software letta dal file VERSION
with open("VERSION") as vf:
    VERSION = vf.read().strip()

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

this_application = None
# Tutti i pin pari come input, dispari come output
ALL_PINS = list(range(2, 28))
INPUT_PINS = [pin for pin in ALL_PINS if pin % 2 == 0]
OUTPUT_PINS = [pin for pin in ALL_PINS if pin % 2 == 1]
binary_inputs = {}
binary_outputs = {}
# Mappa dei pin BCM al numero del pin fisico sulla board
PIN_MAP = {
    2: 3,
    3: 5,
    4: 7,
    5: 29,
    6: 31,
    7: 26,
    8: 24,
    9: 21,
    10: 19,
    11: 23,
    12: 32,
    13: 33,
    14: 8,
    15: 10,
    16: 36,
    17: 11,
    18: 12,
    19: 35,
    20: 38,
    21: 40,
    22: 15,
    23: 16,
    24: 18,
    25: 22,
    26: 37,
    27: 13,
}

# Parametri del dispositivo BACnet
DEFAULT_DEVICE_ID = 110
DEVICE_ID = DEFAULT_DEVICE_ID
DEVICE_NAME = "GardenPi"
VENDOR_ID = 15

# ------------------------------------------------------------------------------
# Helper per aggiungere dinamicamente oggetti BACnet
# ------------------------------------------------------------------------------

def add_object(module_path, class_name, params):
    """Importa dinamicamente e aggiunge un oggetto BACnet all'applicazione."""
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as err:
        logger.error("Impossibile caricare %s.%s: %s", module_path, class_name, err)
        return None

    # Converte l'objectIdentifier da lista a tupla se necessario
    oid = params.get("objectIdentifier")
    if isinstance(oid, list):
        params["objectIdentifier"] = tuple(oid)

    sf = params.get("statusFlags")
    if isinstance(sf, list) and len(sf) == 4:
        params["statusFlags"] = StatusFlags(sf)

    obj = cls(**params)
    try:
        this_application.add_object(obj)
    except RuntimeError as err:
        logger.warning("Impossibile aggiungere l'oggetto %s: %s", params.get("objectName"), err)
        return None
    logger.info("Oggetto aggiunto: %s (%s)", params.get("objectName"), class_name)
    return obj


def load_objects_from_config(config_path="objects.json"):
    """Carica oggetti aggiuntivi da un file JSON con controlli di base."""
    try:
        with open(config_path) as cfg:
            objects = json.load(cfg)
    except FileNotFoundError:
        logger.warning("File di configurazione %s non trovato", config_path)
        return
    except json.JSONDecodeError as err:
        logger.error("Errore di parsing %s: %s", config_path, err)
        return

    # Identificatori gia' utilizzati nell'applicazione
    seen_ids = {
        obj.objectIdentifier
        for obj in list(binary_inputs.values()) + list(binary_outputs.values())
    }
    seen_ids.add(("device", DEVICE_ID))
    for entry in objects:
        module_path = entry.get("module")
        class_name = entry.get("class")
        params = entry.get("params", {})
        if not module_path or not class_name:
            logger.warning("Definizione oggetto non valida: %s", entry)
            continue

        oid = params.get("objectIdentifier")
        if not oid:
            logger.warning("objectIdentifier mancante in %s", entry)
            continue
        oid_tuple = tuple(oid) if isinstance(oid, list) else oid
        if oid_tuple in seen_ids:
            logger.warning("Oggetto con objectIdentifier %s duplicato", oid_tuple)
            continue
        seen_ids.add(oid_tuple)
        params["objectIdentifier"] = oid_tuple

        add_object(module_path, class_name, params)

# Binary Input/Output Objects per GPIO

class CustomBinaryInput(BinaryInputObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'

class CustomBinaryOutput(BinaryOutputObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'
        # store the polarity as a string so that bacpypes can
        # convert it correctly when the property is read
        self.polarity = 'normal'


# Task GPIO
class GPIOUpdateTask(RecurringTask):
    def __init__(self, interval):
        RecurringTask.__init__(self, interval * 1000)
        self.install_task()

    def process_task(self):
        # Aggiorna tutti i Binary Input
        for pin, obj in binary_inputs.items():
            obj.presentValue = 1 if GPIO.input(pin) else 0

        # Aggiorna tutti i Binary Output
        for pin, obj in binary_outputs.items():
            value = 1 if obj.presentValue == 'active' else 0
            if Polarity(getattr(obj, 'polarity', 'normal')) == Polarity('reverse'):
                value = 0 if value == 1 else 1
            GPIO.output(pin, value)

        self.install_task()


def main():
    global this_application, DEVICE_ID
    parser = argparse.ArgumentParser(description="BACnet Pi Server")
    parser.add_argument(
        "-a",
        "--address",
        default="192.168.1.10/24:47808",
        help="Indirizzo BIP (ip/prefix:porta)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="objects.json",
        help="File JSON con oggetti aggiuntivi",
    )
    parser.add_argument(
        "-b",
        "--bbmd",
        help="Indirizzo del BBMD per la registrazione come Foreign Device",
    )
    parser.add_argument(
        "-r",
        "--broadcast-ip",
        help="Indirizzo IP di broadcast (es. 255.255.255.255)",
    )
    parser.add_argument(
        "-d",
        "--device-id",
        type=int,
        default=DEVICE_ID,
        help="ID del dispositivo BACnet",
    )
    args = parser.parse_args()

    DEVICE_ID = args.device_id

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in INPUT_PINS:
        GPIO.setup(pin, GPIO.IN)
    for pin in OUTPUT_PINS:
        GPIO.setup(pin, GPIO.OUT)

    device = LocalDeviceObject(
        objectName=DEVICE_NAME,
        objectIdentifier=("device", DEVICE_ID),
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=VENDOR_ID,
        modelName="Raspberry Pi 4 B",
        vendorName="Nenad Stankovic",
        applicationSoftwareVersion=VERSION,
        firmwareRevision=VERSION,
        systemStatus="operational",
        databaseRevision=Unsigned(0),
        # limit the list to the object types actually supported by bacpypes
        # to avoid errors when the property is read
        protocolObjectTypesSupported=[
            obj
            for obj in ObjectType.enumerations
            if obj
            in getattr(
                importlib.import_module('bacpypes.basetypes'),
                'ObjectTypesSupported',
            ).bitNames
        ],
    )

    this_application = BIPSimpleApplication(device, args.address)

    # Estrae informazioni dall'indirizzo BIP
    ip_port = args.address.split(":")
    iface = ip_interface(ip_port[0])
    ip_addr = str(iface.ip)
    broadcast_ip = args.broadcast_ip if args.broadcast_ip else str(
        iface.network.broadcast_address
    )
    port = int(ip_port[1]) if len(ip_port) > 1 else 0

    if args.broadcast_ip:
        try:
            this_application.ns._localBroadcast = Address(args.broadcast_ip)
        except Exception as err:
            logger.warning(
                "Impossibile impostare broadcast IP personalizzato: %s", err
            )

    if args.bbmd:
        try:
            this_application.register_foreign_device(args.bbmd)
        except Exception as err:
            logger.error("Registrazione BBMD fallita: %s", err)

    for idx, pin in enumerate(INPUT_PINS, start=1):
        bi = CustomBinaryInput(
            objectIdentifier=("binaryInput", idx),
            objectName=f"GPIO{pin}",
            presentValue=0,
            description=f"GPIO{pin} Pin {PIN_MAP.get(pin, pin)}",
        )
        this_application.add_object(bi)
        binary_inputs[pin] = bi

    for idx, pin in enumerate(OUTPUT_PINS, start=1):
        bo = CustomBinaryOutput(
            objectIdentifier=("binaryOutput", idx),
            objectName=f"GPIO{pin}",
            presentValue="inactive",
            description=f"GPIO{pin} Pin {PIN_MAP.get(pin, pin)}",
        )
        this_application.add_object(bo)
        binary_outputs[pin] = bo

    load_objects_from_config(args.config)

    GPIOUpdateTask(5)

    try:
        logger.info(
            "Server BACnet avviato. IP: %s, ID: %s, Porta: %d, Broadcast IP: %s, BBMD: %s",
            ip_addr,
            DEVICE_ID,
            port,
            broadcast_ip,
            args.bbmd if args.bbmd else "Nessuno",
        )
        run()
    except KeyboardInterrupt:
        logger.info("Server BACnet terminato.")
    finally:
        GPIO.cleanup()
        stop()


if __name__ == "__main__":
    main()

