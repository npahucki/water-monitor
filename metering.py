import json
from time import sleep
import traceback
import logging.config
from datetime import datetime

import AWSIoTPythonSDK
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient
from AWSIoTPythonSDK.exception.AWSIoTExceptions import connectTimeoutException

AWS_IOT_ENDPOINT = 'a2irkey2xs1s65-ats.iot.us-east-1.amazonaws.com'

logger = logging.getLogger('metering')


# noinspection PyBroadException
class Metering:
    def __init__(self, readers, client_id, status_handler, update_interval_secs=30):
        self.__running = False
        self.__client_id = client_id
        self.__update_interval_secs = update_interval_secs
        self.__mqtt_client = None
        self.__shadow_client = None
        self.__readers = readers
        self.__shadows = {}
        self.__status_handler = status_handler

    def __shadow_cb(self, payload, status, token):
        if status != 'accepted':
            logger.error('Shadow operation was not accepted: "[%s]". Payload:%s' % (status, payload))
            self.__status_handler.not_ok()

    def __create_shadow_client(self):
        max_offline_queue_size = int((60 / self.__update_interval_secs) * 24 * 10)  # 10 Days worth
        client = AWSIoTMQTTShadowClient(self.__client_id)
        client.configureEndpoint(AWS_IOT_ENDPOINT, 8883)
        client.configureCredentials(CAFilePath="certs/AmazonRootCA1.pem", KeyPath="certs/device/private.pem.key",
                                    CertificatePath="certs/device/certificate.pem.crt")
        client.configureConnectDisconnectTimeout(30)
        client.configureMQTTOperationTimeout(30)
        client.configureAutoReconnectBackoffTime(1, 128, 20)

        # Shared connection with shadow
        mqtt_client = client.getMQTTConnection()
        mqtt_client.configureOfflinePublishQueueing(max_offline_queue_size, AWSIoTPythonSDK.MQTTLib.DROP_OLDEST)
        mqtt_client.configureDrainingFrequency(2)  # Draining: 2 Hz

        logger.debug('Connecting to IOT Cloud MQTT Server....')
        client.connect()
        self.__shadow_client = client
        self.__mqtt_client = mqtt_client

        for reader in self.__readers:
            shadow = self.__shadow_client.createShadowHandlerWithName(reader.name, True)
            shadow.shadowGet(self.__shadow_cb, 60)
            shadow.shadowRegisterDeltaCallback(self.__shadow_cb)
            self.__shadows[reader.name] = shadow

        logger.debug('Connected to IOT Cloud, shadows created')
        return client

    def __publish_reading(self, meter_name, ts, sample_duration, ticks):
        msg = json.dumps({
            'meterName': meter_name,
            'ts': ts,
            'duration': sample_duration,
            'ticks': ticks,
        })
        self.__mqtt_client.publish("water-meter-reading", msg, 0)

    def __update_shadow(self, meter_name, ts, ticks, sample_duration):
        msg = json.dumps({'state': {'reported': {'ticks': ticks, 'ts': ts, 'duration': sample_duration}}})
        self.__shadows[meter_name].shadowUpdate(msg, self.__shadow_cb, 10)

    def __run(self):
        self.__running = True
        self.__status_handler.ok()

        while self.__running:
            try:
                for reader in self.__readers:
                    (sample_start_ts, sample_end_ts, last_ticks, new_ticks) = reader.tally_and_reset()
                    ts = datetime.fromtimestamp(sample_end_ts)
                    sample_seconds = sample_end_ts - sample_start_ts
                    logger.debug('Read reader named "%s" and got %d ticks in %.04f seconds'
                                 % (reader.name, new_ticks, sample_seconds))

                    # When no water is flowing, or is flowing at the same rate as before
                    # And there is no need to update the shadow state this time around.
                    if last_ticks - new_ticks != 0:
                        logger.info('Updating shadow state for "%s" to %d ticks in %.04f seconds' % (reader.name, new_ticks, sample_seconds))
                        self.__update_shadow(reader.name, ts.isoformat(), new_ticks, sample_seconds)

                    if new_ticks > 0:
                        logger.info('Sending consumed message for "%s" with %d ticks in %.04f seconds' % (reader.name, new_ticks, sample_seconds))
                        self.__publish_reading(reader.name, ts.isoformat(), sample_seconds, new_ticks)
                self.__status_handler.ok()
            except Exception:
                self.__status_handler.not_ok()
                logging.error(traceback.format_exc())
            sleep(self.__update_interval_secs)

    def run(self):
        assert not self.__running
        while True:
            try:
                logging.info('Connecting to IOT Cloud')
                self.__create_shadow_client()
                break
            except connectTimeoutException:
                logger.error("Failed to connect MQTT client - timeout (check policy).")
            except Exception:
                self.__status_handler.not_ok()
                logging.error(traceback.format_exc())
        # We are now connected...
        self.__run()
        self.__shadow_client.disconnect()
        self.__status_handler.not_ok()

    def stop(self):
        self.__running = False
