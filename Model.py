#----------------------------------------
# Model...
#   https://datasheets.raspberrypi.com/picow/connecting-to-the-internet-with-pico-w.pdf
#----------------------------------------
def Model():
    from machine import Pin,ADC
    LEVEL=0.3
    ADC=3
    PIN=25
    # Ensure Pin 25 Low...
    thePin=Pin(PIN, mode=Pin.IN, pull=Pin.PULL_DOWN, value=ZERO)
    # Measure ADC Register 3...
    theVoltage=ReadADC(ADC)
    if (theVoltage > LEVEL): # 1/3 VSYS, Not Almost Zero? Test As 0.4 Or Greater
        #
        theModel='Pico'
    if (theVoltage < LEVEL): # Close To Zero? Test As 0.022 Or Slight Greater
        #
        theModel='Pico W'
    #
    Echo("Pico! Voltage {0} V, Model {1}'".format(theVoltage, theModel))
    #
    return theModel