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
    MultiStateValueObject,
)
from bacpypes.local.device import LocalDeviceObject
from bacpypes.task import RecurringTask
from bacpypes.primitivedata import Unsigned
from bacpypes.basetypes import StatusFlags
from bacpypes.primitivedata import ObjectType

# Versione del software letta dal file VERSION
with open("VERSION") as vf:
    VERSION = vf.read().strip()

MODE_INPUT = 1
MODE_OUTPUT = 2
DEFAULT_MODE = MODE_INPUT


# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

this_application = None
INPUT_PINS = [17]
OUTPUT_PINS = [27]
binary_inputs = {}
binary_outputs = {}
msv = None

# Parametri del dispositivo BACnet
DEVICE_ID = 110
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
    this_application.add_object(obj)
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

    seen_ids = set()
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

# Multi-State Value
class CustomMultiStateValue(MultiStateValueObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'
        # abilita la scrittura del presentValue
        if 'presentValue' in self.properties:
            self.properties['presentValue'].writable = True

# Task GPIO
class GPIOUpdateTask(RecurringTask):
    def __init__(self, interval):
        RecurringTask.__init__(self, interval * 1000)
        self.last_mode = msv.presentValue
        self.install_task()

    def process_task(self):
        # Configura i pin di output in base all'Operation_Mode
        mode = msv.presentValue
        if mode != self.last_mode:
            direction = GPIO.IN if mode == MODE_INPUT else GPIO.OUT
            for pin in OUTPUT_PINS:
                GPIO.setup(pin, direction)
            self.last_mode = mode

        # Aggiorna tutti i Binary Input
        for pin, obj in binary_inputs.items():
            obj.presentValue = 1 if GPIO.input(pin) else 0

        # Aggiorna tutti i Binary Output
        if msv.presentValue == MODE_OUTPUT:  # solo in modalità Output
            for pin, obj in binary_outputs.items():
                value = 1 if obj.presentValue == 'active' else 0
                GPIO.output(pin, value)

        self.install_task()


def main():
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
    args = parser.parse_args()

    global this_application, msv

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in INPUT_PINS:
        GPIO.setup(pin, GPIO.IN)
    initial_dir = GPIO.IN if DEFAULT_MODE == MODE_INPUT else GPIO.OUT
    for pin in OUTPUT_PINS:
        GPIO.setup(pin, initial_dir)

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
        protocolObjectTypesSupported=[obj for obj in ObjectType.enumerations],
    )

    this_application = BIPSimpleApplication(device, args.address)

    # Estrae informazioni dall'indirizzo BIP
    ip_port = args.address.split(":")
    iface = ip_interface(ip_port[0])
    ip_addr = str(iface.ip)
    broadcast_ip = str(iface.network.broadcast_address)
    port = int(ip_port[1]) if len(ip_port) > 1 else 0

    if args.bbmd:
        try:
            this_application.register_foreign_device(args.bbmd)
        except Exception as err:
            logger.error("Registrazione BBMD fallita: %s", err)

    for idx, pin in enumerate(INPUT_PINS, start=1):
        bi = CustomBinaryInput(
            objectIdentifier=("binaryInput", idx),
            objectName=f"GPIO_{pin}_Input",
            presentValue=0,
        )
        this_application.add_object(bi)
        binary_inputs[pin] = bi

    for idx, pin in enumerate(OUTPUT_PINS, start=1):
        bo = CustomBinaryOutput(
            objectIdentifier=("binaryOutput", idx),
            objectName=f"GPIO_{pin}_Output",
            presentValue="inactive",
        )
        this_application.add_object(bo)
        binary_outputs[pin] = bo

    msv = CustomMultiStateValue(
        objectIdentifier=("multiStateValue", 1),
        objectName="Operation_Mode",
        presentValue=DEFAULT_MODE,
        numberOfStates=2,
        stateText=["Input", "Output"],
    )
    this_application.add_object(msv)

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

