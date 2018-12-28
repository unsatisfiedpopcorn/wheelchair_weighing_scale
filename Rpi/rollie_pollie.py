#!/usr/bin/env python3
from lib.hx711 import HX711  # import the class HX711
import RPi.GPIO as GPIO  # import GPIO
from lib.arduino_nfc import SerialNfc
from lib.scale_observer import ScaleObserver
from lib.state import State
from time import sleep
from Adafruit_CharLCD import Adafruit_CharLCD
from config import (
    NUMBER_OF_READINGS,
    NFC_PORT,
    CLOCK_PIN, DATA_PIN, TARE_BTN_PIN, REGISTRATION_BTN_PIN,
    CHANNEL, GAIN, SCALE)


# RolliePollie integrates both the weighing scale and NFC reader. It acts as the controller.
class RolliePollie:

    def __init__(self):

        # Create an object hx which represents your real hx711 chip
        # Required input parameters are only 'dout_pin' and 'pd_sck_pin'
        # If you do not pass any argument 'gain_channel_A' then the default value is 128
        # If you do not pass any argument 'set_channel' then the default value is 'A'
        # you can set a gain for channel A even though you want to currently select channel B
        self._scale = HX711(dout_pin=DATA_PIN, pd_sck_pin=CLOCK_PIN, gain_channel_A=GAIN, select_channel=CHANNEL)
        self._ser_nfc = SerialNfc(NFC_PORT, baudrate=9600)
        self._observer = ScaleObserver()
        self._memoized_tag_data = None
        self._state = State.DEFAULT

        # setup
        self.setup_gpio()
        self.setup_scale()
        self._observer.on_scale_dismount(self.flush_tag_data_callback)
        self._observer.on_successful_weighing(self.test_callback)

        # instantiate lcd and specify pins
        # GPIO.setup(11, GPIO.OUT)
        self.lcd = Adafruit_CharLCD(rs=RS_PIN, en=EN_PIN,
                               d4=D4_PIN, d5=D5_PIN, d6=D6_PIN, d7=D7_PIN,
                               cols=16, lines=2)
        self.lcd.clear()
    # Callbacks ###
    def test_callback(self, weight):
        print("Tested")

    def flush_tag_data_callback(self):
        self._memoized_tag_data = None

    def tare_callback(self, channel):
        self._scale.zero(times=10)
        print("Tared via trigger on channel {}".format(channel))

    def register_callback(self, channel):
        wheelchair_weight = self._scale.get_weight_mean(NUMBER_OF_READINGS)
        self._ser_nfc.write_weight(wheelchair_weight)
        print("updated wheelchair weight to {}".format(wheelchair_weight))

    # Setups ###
    def setup_scale(self):
        # Keeps resetting until scale is ready
        while not self._scale.reset():
            print("resetting")
            pass
        # measure tare and save the value as offset for current channel and gain selected.
        # keeps looping until properly zeroed
        while not self._scale.zero(times=10):
            print("zeroing")
            pass
        self._scale.set_scale_ratio(scale_ratio=SCALE)  # set ratio for current channel

    def setup_gpio(self):
        """
        :rtype: void
        """
        GPIO.setmode(GPIO.BCM)

        # Falling edge triggers interrupt #

        # Setup for taring functionality
        GPIO.setup(TARE_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(TARE_BTN_PIN,
                              GPIO.FALLING,
                              callback=self.tare_callback,
                              bouncetime=300)

        # Setup for registration functionality
        GPIO.setup(REGISTRATION_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(REGISTRATION_BTN_PIN,
                              GPIO.FALLING,
                              callback=self.register_callback,
                              bouncetime=300)

    def run(self):
        """
        Main logic for RolliePollie weighing scale
        """
        try:
            result = self._scale.reset()  # Before we start, reset the hx711 ( not necessary)
            if result:  # you can check if the reset was successful
                print('Ready to use')
            else:
                print('not ready')

            # if you need the data fast without doing average or filtering them.
            # do some kind of loop and do not pass any argument. Default 'times' is 1
            # be aware that HX711 sometimes return invalid or wrong data.
            # you can probably see it now
            print('Weight taking the average of {} reading(s):'.format(NUMBER_OF_READINGS))
            while True:
                # the value will vary because it is only one immediate reading.
                # the default speed for hx711 is 10 samples per second
                tag_data = self._ser_nfc.get_weight()
                total_weight = self._scale.get_weight_mean(NUMBER_OF_READINGS)
                self._observer.weight = total_weight

                if tag_data:  # Memoizes a new tag data if presented with one
                    self._memoized_tag_data = tag_data
                    weight = '{:.1f}kg'.format((total_weight - self._memoized_tag_data.wheelchair_weight) / 1000)

                elif self._memoized_tag_data:  # In the absence of tag data, use last memoized tag data
                    weight = '{:.1f}kg'.format((total_weight - self._memoized_tag_data.wheelchair_weight) / 1000)

                else:  # If there is no available tag data, perform as a normal weighing scale
                    weight = '{:.1f}kg'.format(total_weight / 1000)
                
                self.lcd.clear()
                self.lcd.message(weight)
                print(weight)
        except (KeyboardInterrupt, SystemExit):
            print('\nGPIO cleaned up, serial closed(if opened)\n Bye (:')

        finally:
            GPIO.cleanup()
            self._ser_nfc.close()


if __name__ == '__main__':
    RolliePollie().run()
