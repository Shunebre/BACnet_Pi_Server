import logging
import json
import importlib
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


# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configura i pin GPIO
INPUT_PINS = [17]
OUTPUT_PINS = [27]

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin in INPUT_PINS:
    GPIO.setup(pin, GPIO.IN)
for pin in OUTPUT_PINS:
    GPIO.setup(pin, GPIO.OUT)

# Parametri del dispositivo BACnet
DEVICE_ID = 110
DEVICE_NAME = "GardenPi"
VENDOR_ID = 15

# Crea un oggetto Device
device = LocalDeviceObject(
    objectName=DEVICE_NAME,
    objectIdentifier=('device', DEVICE_ID),
    maxApduLengthAccepted=1024,
    segmentationSupported="segmentedBoth",
    vendorIdentifier=VENDOR_ID,
)

# Proprietà custom
device.modelName = "Raspberry Pi 4 B"
device.vendorName = "Nenad Stankovic"
device.applicationSoftwareVersion = "1.0.0"
device.firmwareRevision = "1.0.0"
device.systemStatus = 'operational'
device.databaseRevision = Unsigned(0)

# Crea l'applicazione BACnet
this_application = BIPSimpleApplication(device, '192.168.1.10/24:47808')

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

    obj = cls(**params)
    this_application.add_object(obj)
    logger.info("Oggetto aggiunto: %s (%s)", params.get("objectName"), class_name)
    return obj


def load_objects_from_config(config_path="objects.json"):
    """Carica oggetti aggiuntivi da un file JSON."""
    try:
        with open(config_path) as cfg:
            objects = json.load(cfg)
    except FileNotFoundError:
        logger.warning("File di configurazione %s non trovato", config_path)
        return
    except json.JSONDecodeError as err:
        logger.error("Errore di parsing %s: %s", config_path, err)
        return

    for entry in objects:
        module_path = entry.get("module")
        class_name = entry.get("class")
        params = entry.get("params", {})
        if not module_path or not class_name:
            logger.warning("Definizione oggetto non valida: %s", entry)
            continue
        add_object(module_path, class_name, params)

# Binary Input/Output Objects for GPIO
binary_inputs = {}
binary_outputs = {}

class CustomBinaryOutput(BinaryOutputObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'

for idx, pin in enumerate(INPUT_PINS, start=1):
    bi = BinaryInputObject(
        objectIdentifier=('binaryInput', idx),
        objectName=f'GPIO_{pin}_Input',
        presentValue=0,
    )
    this_application.add_object(bi)
    binary_inputs[pin] = bi

for idx, pin in enumerate(OUTPUT_PINS, start=1):
    bo = CustomBinaryOutput(
        objectIdentifier=('binaryOutput', idx),
        objectName=f'GPIO_{pin}_Output',
        presentValue='inactive',
    )
    this_application.add_object(bo)
    binary_outputs[pin] = bo

# Multi-State Value
class CustomMultiStateValue(MultiStateValueObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'

msv = CustomMultiStateValue(
    objectIdentifier=('multiStateValue', 1),
    objectName='Operation_Mode',
    presentValue=1,
    numberOfStates=3,
    stateText=["Off", "Manual", "Automatic"],
)
this_application.add_object(msv)


# Carica eventuali oggetti aggiuntivi definiti in objects.json
load_objects_from_config()

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
            GPIO.output(pin, value)

        self.install_task()

GPIOUpdateTask(5)  # ogni 5 secondi

try:
    logger.info("Server BACnet avviato.")
    run()
except KeyboardInterrupt:
    logger.info("Server BACnet terminato.")
finally:
    GPIO.cleanup()
    stop()
