import datetime
from datetime import datetime


class WaterMeterDeviceReader:
    def __init__(self, name, pi_gpio, pin):
        self.name = name
        self.__last_tally = 0
        self.__ts = datetime.datetime.now().timestamp()

        pi_gpio.set_mode(pin, pi_gpio.INPUT)
        pi_gpio.set_pull_up_down(pin, pi_gpio.PUD_UP)

        self.__cb = pi_gpio.callback(pin, pi_gpio.EITHER_EDGE)

    def tally_and_reset(self):
        now = datetime.datetime.now().timestamp()
        new_tally = self.__cb.tally()
        last_tally = self.__last_tally
        sample_start = self.__ts
        sample_end = now

        self.__ts = now
        self.__last_tally = new_tally

        return sample_start, sample_end, last_tally, new_tally
