import logging
import RPi.GPIO as GPIO
import Adafruit_DHT
import Adafruit_DHT.common as dht_common  # Fix per "Unknown platform"

from bacpypes.core import run, stop
from bacpypes.app import BIPSimpleApplication
from bacpypes.object import (
    AnalogValueObject,
    BinaryValueObject,
    MultiStateValueObject,
)
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
# Gestiamo tutti i pin disponibili tramite BCM
GPIO_PINS = [
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
    14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 26, 27,
]
DHT_PIN = 4  # pin GPIO per DHT11

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin in GPIO_PINS:
    GPIO.setup(pin, GPIO.IN)

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

# Oggetti BinaryValue e MultiStateValue per ogni GPIO
class CustomBinaryValue(BinaryValueObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'


class CustomMultiStateValue(MultiStateValueObject):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.statusFlags = StatusFlags([False, False, False, False])
        self.outOfService = False
        self.eventState = 'normal'


gpio_bv_objects = {}
gpio_mode_objects = {}

bv_index = 1
mv_index = 1
for pin in GPIO_PINS:
    bv = CustomBinaryValue(
        objectIdentifier=('binaryValue', bv_index),
        objectName=f'GPIO_{pin}_BV',
        presentValue='inactive',
    )
    this_application.add_object(bv)
    gpio_bv_objects[pin] = bv
    bv_index += 1

    mv = CustomMultiStateValue(
        objectIdentifier=('multiStateValue', mv_index),
        objectName=f'GPIO_{pin}_Mode',
        presentValue=1,
    )
    mv.numberOfStates = 2
    mv.stateText = ['Lettura', 'Lettura/Scrittura']
    this_application.add_object(mv)
    gpio_mode_objects[pin] = mv
    mv_index += 1

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
        self.pin_modes = {pin: GPIO.IN for pin in GPIO_PINS}
        self.install_task()

    def process_task(self):
        for pin in GPIO_PINS:
            mode = gpio_mode_objects[pin].presentValue
            if mode == 1:
                if self.pin_modes[pin] != GPIO.IN:
                    GPIO.setup(pin, GPIO.IN)
                    self.pin_modes[pin] = GPIO.IN
                val = GPIO.input(pin)
                gpio_bv_objects[pin].presentValue = (
                    'active' if val else 'inactive'
                )
            else:
                if self.pin_modes[pin] != GPIO.OUT:
                    GPIO.setup(pin, GPIO.OUT)
                    self.pin_modes[pin] = GPIO.OUT
                output_value = (
                    1 if gpio_bv_objects[pin].presentValue == 'active' else 0
                )
                GPIO.output(pin, output_value)

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
