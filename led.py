from pigpio import OUTPUT


class LED:
    def __init__(self, pi_gpio, pin):
        pi_gpio.set_mode(pin, OUTPUT)
        self.__pi_gpio = pi_gpio
        self.__pin = pin

    def on(self):
        self.__pi_gpio.write(self.__pin, 1)

    def off(self):
        self.__pi_gpio.write(self.__pin, 0)
