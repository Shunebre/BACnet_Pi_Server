import logging
import json
import importlib
import RPi.GPIO as GPIO
import Adafruit_DHT
import Adafruit_DHT.common as dht_common  # Fix per "Unknown platform"

from bacpypes.core import run, stop
from bacpypes.app import BIPSimpleApplication
from bacpypes.object import BinaryInputObject, BinaryOutputObject, AnalogValueObject
from bacpypes.local.device import LocalDeviceObject
from bacpypes.task import RecurringTask
from bacpypes.primitivedata import Unsigned
from bacpypes.basetypes import StatusFlags

# Forza la piattaforma a 'Raspberry Pi'
dht_common.get_platform = lambda: 'Raspberry Pi'

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configura i pin GPIO
INPUT_PIN = 17
OUTPUT_PIN = 27
DHT_PIN = 4  # pin GPIO per DHT11

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(INPUT_PIN, GPIO.IN)
GPIO.setup(OUTPUT_PIN, GPIO.OUT)

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

# Binary Input
bi = BinaryInputObject(
    objectIdentifier=('binaryInput', 1),
    objectName='GPIO_17_Input',
    presentValue=0
)
this_application.add_object(bi)

# Binary Output
class CustomBinaryOutput(BinaryOutputObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'

bo = CustomBinaryOutput(
    objectIdentifier=('binaryOutput', 1),
    objectName='GPIO_27_Output',
    presentValue='inactive'
)
this_application.add_object(bo)

# Analog Value
class CustomAnalogValue(AnalogValueObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'

av = CustomAnalogValue(
    objectIdentifier=('analogValue', 1),
    objectName='Temperature_AV',
    presentValue=0.0
)
this_application.add_object(av)

# Carica eventuali oggetti aggiuntivi definiti in objects.json
load_objects_from_config()

# Task GPIO e DHT11
class GPIOUpdateTask(RecurringTask):
    def __init__(self, interval):
        RecurringTask.__init__(self, interval * 1000)
        self.install_task()

    def process_task(self):
        # Leggi lo stato del Binary Input
        value = GPIO.input(INPUT_PIN)
        bi.presentValue = 1 if value else 0

        # Scrivi lo stato del Binary Output
        output_value = 1 if bo.presentValue == 'active' else 0
        GPIO.output(OUTPUT_PIN, output_value)

        # Leggi la temperatura dal DHT11 e aggiorna l'AnalogValue
        humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, DHT_PIN)
        if temperature is not None:
            av.presentValue = float(temperature)
        else:
            av.presentValue = 0.0  # fallback

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
