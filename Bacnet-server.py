import logging
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
