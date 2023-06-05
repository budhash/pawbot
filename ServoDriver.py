# Pico Servo Driver
# ServoDriver: uses the PIO state machines to drive a servo
from machine import Pin
from rp2 import PIO, StateMachine, asm_pio
from time import sleep


class InternalServoDriverException(Exception):
    pass

class UnregisteredServoException(Exception):
    pass

class InvalidServoSettingException(Exception):
    pass

class ServoDriver:
    """
    Driver class used to control servos using the PIO state machines
    """
    # servo : 0 degrees -> pulse of 0.5ms, 180 degrees 2.5ms
    # pulse train freq 50hz - 20mS
    # 1uS is freq of 1000000
    # servo pulses range from 500 to 2500usec and overall pulse train is 20000usec repeat
    MIN_SERVO_PULSE = 500
    MAX_SERVO_PULSE = 2500
    PULSE_TRAIN = 20000
    DEGREES_TO_PULSE_LEN = 2000/180
    
    # this code drives a pwm on the PIO. It is running at 2Mhz, which gives the PWM a 1uS resolution. 
    @asm_pio(sideset_init=PIO.OUT_LOW)
    def _servo_pwm():
        """
        Private method to generate the pulse width modulation signal required by the servo
        """
        # first we clear the pin to zero, then load the registers. Y is always 20000 - 20uS, x is the pulse 'on' length.     
        pull(noblock) .side(0)
        mov(x, osr) # keep most recent pull data stashed in X, for recycling by noblock
        mov(y, isr) # ISR must be preloaded with PWM count max
        # this is where the looping work is done. the overall loop rate is 1Mhz (clock is 2Mhz - we have 2 instructions to do)    
        label("loop")
        jmp(x_not_y, "skip") # if there is 'excess' Y number leave the pin alone and jump to the 'skip' label until we get to the X value
        nop()         .side(1)
        label("skip")
        jmp(y_dec, "loop") #count down y by 1 and jump to pwmloop. When y is 0 we will go back to the 'pull' command
             
    # simply stops and starts the servo PIO, so the pin could be used for soemthing else.
    def register_servo(self, servo: int) -> None:
        """
        Registers a servo with the ServoDriver by activating its state machine

        Parameters:
            servo (int): The index of the servo to register.
        """
        if(not self.servos[servo].active()):
            self.servos[servo].active(1)

    def unregister_servo(self, servo: int) -> None:
        """
        Unregisters a servo from the ServoDriver by deactivating its state machine

        Parameters:
            servo (int): The index of the servo to unregister
        """
        if(self.servos[servo].active()):
            self.servos[servo].active(0)

    def get_servo_angle(self, servo: int) -> int:
        """
        Returns the current angle of a given servo

        Parameters:
            servo (int): The index of the servo

        Returns:
            int: The current angle of the servo

        Raises:
            UnregisteredServoException: If invalid servo is passed
        """
        self.__validate_servo(servo)
        return self.servo_angles[servo]

    def set_servo_angle(self, servo: int, degrees: int) -> None:
        """
        Sets the angle of a given servo

        Parameters:
            servo (int): The index of the servo
            degrees (int): The desired angle for the servo

        Raises:
            UnregisteredServoException: If invalid servo is passed
            InvalidServoSettingException: If the desired angle exceeds the maximum angle
        """
        self.__servo_angle(servo, degrees)
        
    def set_servo_angle_smooth(self, servo: int, degrees: int, delay: float = 0.01, step: int = 1) -> None:
        """
        Smoothly sets the angle of a given servo by moving in small steps

        Parameters:
            servo (int): The index of the servo
            degrees (int): The final desired angle for the servo
            delay (float, optional): The delay between each step. Default is 0.01
            step (int, optional): The size of each step. Default is 1

        Raises:
            UnregisteredServoException: If invalid servo is passed
            InvalidServoSettingException: If the desired angle exceeds the maximum angle
        """
        current_angle = self.servo_angles[servo]
        if degrees < current_angle:
            for angle in range(current_angle, degrees - 1, -step):
                self.__servo_angle(servo, angle)
                sleep(delay)
        else:
            for angle in range(current_angle, degrees + 1, step):
                self.__servo_angle(servo, angle)
                sleep(delay)

    def __calc_pulse_length(self, degrees: int) -> int:
        """
        Private method that calculates the pulse length corresponding to a given angle

        Parameters:
            degrees (int): The angle

        Returns:
            int: The pulse length corresponding to the angle
        """
        return int(degrees * self.DEGREES_TO_PULSE_LEN + self.MIN_SERVO_PULSE)

    # set_servo_angle takes a degree position for the servo to goto. 
    # 0 degrees->180 degrees is 0->2000us, plus offset of 500uS
    # 1 degree ~ 11uS.
    # this function does the sum then calls __write_servo to actually poke the PIO 
    def __servo_angle(self, servo: int, degrees: int) -> None:
        """
        Private method that sets the angle of a given servo and keeps a track of the current angle

        Parameters:
            servo (int): The index of the servo
            degrees (int): The desired angle for the servo

        Raises:
            UnregisteredServoException: If invalid servo is passed
            InvalidServoSettingException: If the desired angle exceeds the maximum angle
        """
        self.__validate_servo(servo)
        self.__validate_angle(degrees)
        pulse_length = self.__calc_pulse_length(degrees)
        self.__write_servo(servo, pulse_length)
        self.servo_angles[servo] = degrees
    
    def __write_servo(self, servo: int, pulse_length: int) -> None:
        """
        Private method that writes the pulse length to a given servo and actually changes the servo angle

        Parameters:
            servo (int): The index of the servo
            pulse_length (int): The pulse length to write to the servo

        """
        if(pulse_length < self.MIN_SERVO_PULSE):
            pulse_length = self.MIN_SERVO_PULSE
        if(pulse_length > self.MAX_SERVO_PULSE):
            pulse_length = self.MAX_SERVO_PULSE
        # check if servo SM is active, otherwise we are trying to control a thing we do not have control over
        if self.servos[servo].active():
            self.servos[servo].put(pulse_length)

    def __validate_servo(self, servo: int) -> None:
        """
        Validates if the given servo is registered

        Parameters:
            servo (int): The index of the servo

        Raises:
            UnregisteredServoException: If invalid servo is passed
        """
        if(not self.servos[servo].active()):
            raise UnregisteredServoException(f"Servo is unknown or unregistered: {servo}")

    def __validate_angle(self, degrees: int) -> None:
        """
        Validates if the given angle does not exceed the maximum angle

        Parameters:
            degrees (int): The angle to validate

        Raises:
            InvalidServoSettingException: If the angle exceeds the maximum angle
        """
        if degrees > self.max_angle:
            raise InvalidServoSettingException(f"Desired angle {degrees} exceeds maximum angle {self.max_angle}.")

    # class initialisation
    # defaults to the standard pins and freq for the kitronik board, but could be overridden
    # servo pins on the Simply Servos board are: GP2, GP3, GP4, GP5, GP6, GP7, GP8, GP9 for servos 1-8 in order
    def __init__(self, servo_pins: List[int] = [2,3,4,5,6,7,8,9], max_angle = 180, initial_angle: int = 90):
        """
        Initializes the ServoDriver with a given list of servo pins and sets all servos to an initial angle

        Parameters:
            servo_pins (List[int], optional): A list of servo pins. Default is [2,3,4,5,6,7,8,9]
            initial_angle (int, optional): The initial angle for all servos. Default is 90
        """
        self.servo_count = len(servo_pins)
        self.servo_pins = servo_pins
        self.used_state_machines = [False] * self.servo_count
        self.servos = []
        self.servo_angles = [0] * self.servo_count  # initialize empty list for servo angles
        self.max_angle = max_angle

        # connect the servos by default on initialization
        for i in range(self.servo_count):
            for j in range(self.servo_count): # StateMachine range based on servo_pins
                if self.used_state_machines[j]:
                    continue # ignore this index if already used
                try:
                    self.servos.append(StateMachine(j, self._servo_pwm, freq=2000000, sideset_base=Pin(self.servo_pins[i])))
                    self.used_state_machines[j] = True # set this index to used
                    break 
                except ValueError:
                    pass # external resouce has SM, move on
                if j == self.servo_count - 1:
                    # cannot find an unused SM
                    raise ValueError("Could not claim a StateMachine, all in use")
                
            self.servos[i].put(self.PULSE_TRAIN)
            self.servos[i].exec("pull()")
            self.servos[i].exec("mov(isr, osr)")
            self.register_servo(i)
            self.__servo_angle(i, initial_angle)
