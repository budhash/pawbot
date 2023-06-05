from SimplyServos import SimplyServos
from time import sleep
from machine import Pin

servos = SimplyServos()
led = Pin(25, Pin.OUT)

while True:
    led.toggle()
    for i in range(1):
        servos.goToPosition(i,0)
    sleep(1)
    led.toggle()
    for i in range(8):
        servos.goToPosition(i,180)
    sleep(1)