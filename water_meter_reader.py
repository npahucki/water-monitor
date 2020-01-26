from datetime import datetime
from pigpio import INPUT, PUD_UP, EITHER_EDGE

class WaterMeterDeviceReader:
    def __init__(self, name, pi_gpio, pin):
        self.name = name
        self.__last_tally = -1
        self.__ts = datetime.now().timestamp()

        pi_gpio.set_mode(pin, INPUT)
        pi_gpio.set_pull_up_down(pin, PUD_UP)

        self.__cb = pi_gpio.callback(pin, EITHER_EDGE)

    def tally_and_reset(self):
        new_tally = self.__cb.tally()
        self.__cb.reset_tally()

        now = datetime.now().timestamp()
        last_tally = self.__last_tally
        sample_start = self.__ts
        sample_end = now

        self.__ts = now
        self.__last_tally = new_tally

        return sample_start, sample_end, last_tally, new_tally
