import os
import pigpio
import traceback
import socket
import logging.config
from led import LED
from metering import Metering
from water_meter_reader import WaterMeterDeviceReader
from water_meter_reader_mock import MockWaterMeterDeviceReader

GREEN_LED_PIN = 11
RED_LED_PIN = 9
JIMENEZ_SENSOR_PIN = 14
PAHUCKI_SENSOR_PIN = 15

logging.config.fileConfig(os.environ.get('LOGGING_CONF', default='logging.conf'))


class LedStatusHandler:
    def __init__(self, green_led, red_led):
        self.__green = green_led
        self.__red = red_led
        self.__green.off()
        self.__red.off()

    def ok(self):
        self.__green.on()
        self.__red.off()

    def not_ok(self):
        self.__green.off()
        self.__red.on()

class LogStatusHandler:
    def __init__(self):
        self.__logger =  logging.getLogger('status')

    def ok(self):
        self.__logger.info('STATUS IS NOW: OK')

    def not_ok(self):
        self.__logger.warning('STATUS IS NOW: NOT OK')


logger = logging.getLogger('monitoring')

def main():
    if os.environ.get('MOCK', default='0') == '1':
        status_handler = LogStatusHandler()
        readers = [
            MockWaterMeterDeviceReader('TestMeter1'),
            MockWaterMeterDeviceReader('TestMeter2'),
        ]
    else:
        pi = pigpio.pi()
        status_handler = LedStatusHandler(green_led=LED(pi, GREEN_LED_PIN), red_led=LED(pi, RED_LED_PIN))
        readers = [
            WaterMeterDeviceReader('JimenezWaterMeter', pi, JIMENEZ_SENSOR_PIN),
            WaterMeterDeviceReader('PahuckiWaterMeter', pi, PAHUCKI_SENSOR_PIN)
        ]

    metering = None
    try:
        logger.info('Starting metering...')
        metering = Metering(readers, socket.gethostname(), status_handler, 5)
        status_handler.ok()
        metering.run()
    except Exception:
        logger.critical('Exiting due to unexpected error %s' % traceback.format_exc())
        status_handler.not_ok()
    except KeyboardInterrupt:
        logger.info('Exiting at user request...')
        status_handler.not_ok()

    logger.info('Stopping metering...')
    metering.stop()
    logger.info('Done.')


if __name__ == '__main__':
    main()
