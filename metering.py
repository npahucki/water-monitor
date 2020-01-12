import json
from time import sleep
from water_meter_reader import WaterMeterDeviceReader
import traceback
import logging
import logging.config

import AWSIoTPythonSDK
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import connectTimeoutException

AWS_IOT_ENDPOINT='a2irkey2xs1s65-ats.iot.us-east-1.amazonaws.com'
DEFAULT_CLOUD_UPDATE_INTERVAL_SECS = 1
TICKS_PER_LITER = 12

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('metering')

class Metering:
    def __init__(self, readers, client_id = None, update_interval_secs = DEFAULT_CLOUD_UPDATE_INTERVAL_SECS):
        self.__running = False
        self.__client_id = client_id
        self.__update_interval_secs = update_interval_secs
        self.__mqtt_client = None
        self.__shadow_client = None
        self.__readers = readers
        self.__shadows = {}


    def __shadow_cb(self, payload, status, token):
        if status != 'accepted':
            logger.error('Shadow operation was not accepted: "[%s]". Payload:%s' % (status, payload))

    def __create_shadow_client(self):
        max_offline_queue_size = int((60 / self.__update_interval_secs) * 24 * 10)  # 10 Days worth
        client = AWSIoTMQTTShadowClient(self.__client_id)
        client.configureEndpoint(AWS_IOT_ENDPOINT, 8883)
        client.configureCredentials(CAFilePath="certs/AmazonRootCA1.pem", KeyPath="certs/device/private.pem.key", CertificatePath="certs/device/certificate.pem.crt")
        client.configureConnectDisconnectTimeout(30)  # 10 sec
        client.configureMQTTOperationTimeout(5)  # 5 sec
        client.configureAutoReconnectBackoffTime(1, 128, 20)

        # Shared connection with shadow
        mqtt_client = client.getMQTTConnection()
        mqtt_client.configureOfflinePublishQueueing(max_offline_queue_size, AWSIoTPythonSDK.MQTTLib.DROP_OLDEST)
        mqtt_client.configureDrainingFrequency(2)  # Draining: 2 Hz


        client.connect()
        self.__shadow_client = client
        self.__mqtt_client = mqtt_client

        for reader in self.__readers:
            shadow = self.__shadow_client.createShadowHandlerWithName(reader.name, True)
            shadow.shadowGet(self.__shadow_cb, 5)
            shadow.shadowRegisterDeltaCallback(self.__shadow_cb)
            self.__shadows[reader.name] = shadow

        return client

    def __publish_reading(self, meter_name, liters_consumed, current_liters_per_minute):
        msg = json.dumps({
            'meterName': meter_name,
            'litersConsumed' : liters_consumed,
            'litresPerMinute': current_liters_per_minute,
        })
        self.__mqtt_client.publish("water-meter-reading", msg, 0)

    def __update_shadow(self, meter_name, current_liters_per_minute):
        msg = json.dumps({'state': {'reported': { 'lpm': current_liters_per_minute}}})
        self.__shadows[meter_name].shadowUpdate(msg, self.__shadow_cb, 10)

    def __run(self):
        self.__running = True
        while self.__running:
            for reader in self.__readers:
                (sample_start_ts, sample_end_ts, former_tally, current_tally) = reader.tally_and_reset()
                liters_consumed = current_tally / TICKS_PER_LITER
                sample_seconds = sample_end_ts - sample_start_ts
                liters_per_minute = current_tally / (sample_seconds * 60)
                logger.debug('Read reader named "%s" and got %d ticks in %f seconds'
                              % (reader.name, current_tally, sample_seconds))

                # Detect Liters Per minute has changed
                # When no water is flowing, or is flowing at the same rate as before
                # And there is no need to update the shadow state this time around.
                if former_tally != current_tally:
                    logger.debug('Updating shadow state to %.04f lpm' % liters_per_minute)
                    self.__update_shadow(reader.name, liters_per_minute)

                if liters_consumed > 0:
                    logger.debug('Sending consumed message %d consumed with a current lpm of %.04f'
                                % (liters_consumed, liters_per_minute))
                    self.__publish_reading(reader.name, liters_consumed, liters_per_minute)

            sleep(self.__update_interval_secs)

    def start(self):
        assert not self.__running
        self.__create_shadow_client()
        self.__run()
        self.__shadow_client.disconnect()

    def stop(self):
        self.__running = False


def main():
    # TODO: When in mock mode, pass none for pins so it behaves like a mock
    metering = None
    readers = [
        WaterMeterDeviceReader('JimenezWaterMeter', gpio_pin=None),
        WaterMeterDeviceReader('PahuckiWaterMeter', gpio_pin=None)
    ]

    try:
        logger.info('Starting metering')
        metering = Metering(readers, 'test-client', 5)
        metering.start()
    except connectTimeoutException:
        logger.error("Failed to connect MQTT client - timeout (check policy). Exiting!")
    except Exception:
        logger.error('Exiting due to unexpected error %s' % traceback.format_exc())

    logger.info('Done.')


if __name__ == '__main__':
    main()

