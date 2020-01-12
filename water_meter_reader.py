import threading
import time
import random
import datetime
import threading

class WaterMeterDeviceReader:
    def __init__(self, name, gpio_pin=None):
        self.name = name
        self.__tally = 0
        self.__last_tally = 0
        self.__ts = datetime.datetime.now().timestamp()
        self.__lock = threading.Lock()


        if gpio_pin:
            # TODO: Setting up pigpio for callbacks
            pass
        else:
            # Go into mock mode
            thread = threading.Thread(target=self.__mock_run, args=())
            thread.daemon = True
            thread.start()

    def __mock_run(self):
            while True:
                self.__inc_tally(random.randint(0, 40))
                time.sleep(1)

    def __inc_tally(self, add):
        self.__lock.acquire()
        self.__tally = self.__tally + add
        self.__lock.release()


    def tally_and_reset(self):
        now = datetime.datetime.now().timestamp()
        self.__lock.acquire()
        last_tally = self.__last_tally
        last_ts = self.__ts
        self.__last_tally = self.__tally
        self.__tally = 0
        self.__ts = now
        self.__lock.release()
        return (last_ts, now, last_tally, self.__last_tally)
