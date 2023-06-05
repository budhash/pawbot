from ServoDriver import ServoDriver

class Leg:
    def __init__(self, hipServoId, kneeServoId, servoDriver, mirror = False):
        self.hipServoId = hipServoId
        self.kneeServoId = kneeServoId
        self.mirror = mirror
        self.driver = servoDriver
        
    def __resolve(self, angle):
        if self.mirror:
            return 180 - angle
        else:
            return angle
    
    def hip(self, angle):
        self.driver.setPosition(self.hipServoId, self.__resolve(angle))

    def knee(self, angle):
        self.driver.setPosition(self.kneeServoId, self.__resolve(angle))
        
    def forward_stretch(self):
        self.hip(0)
        self.knee(90)
        
    def forward_fold(self):
        self.hip(0)
        self.knee(170)

    def stand(self):
        self.hip(135)
        self.knee(0)
        
    def hover(self):
        self.hip(90)
        self.knee(90)

class RoboDog:
    
    def __init__(self):
        self.driver = ServoDriver()
        self.rightFrontLeg = Leg(0,1,self.driver,True)
        self.rightHindLeg = Leg(2,3,self.driver,True)
        self.leftFrontLeg = Leg(4,5,self.driver,False)
        self.leftHindLeg = Leg(6,7,self.driver,False)
        
    def forward_stretch(self):
        self.rightFrontLeg.forward_stretch()
        self.leftFrontLeg.forward_stretch()
        self.rightHindLeg.forward_stretch()
        self.leftHindLeg.forward_stretch()

    def forward_fold(self):
        self.rightFrontLeg.forward_fold()
        self.leftFrontLeg.forward_fold()
        self.rightHindLeg.forward_fold()
        self.leftHindLeg.forward_fold()
        
    def stand(self):
        self.rightFrontLeg.stand()
        self.leftFrontLeg.stand()
        self.rightHindLeg.stand()
        self.leftHindLeg.stand()
        
    def hover(self):
        self.rightFrontLeg.hover()
        self.leftFrontLeg.hover()
        self.rightHindLeg.hover()
        self.leftHindLeg.hover()
        

