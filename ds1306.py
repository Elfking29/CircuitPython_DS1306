# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2026 Avery Ramsey
#
# SPDX-License-Identifier: MIT
"""
`ds1306`
================================================================================

CircuitPython Driver for the DS1306 Real Time Clock from Maxim Integrated


* Author(s): Avery Ramsey

Implementation Notes
--------------------

**Hardware:**

* DS1306 Real Time Clock

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

#imports
from digitalio import DigitalInOut, Direction

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/Elfking29/CircuitPython_DS1306.git"

class DS1306:
    
    def __init__(self,sclk,mosi,miso,cs):
        self.__cs=DigitalInOut(cs)
        self.__cs.direction = Direction.OUTPUT
        self.__cs.value=False
        
        try:
            import busio
            self.__spi=busio.SPI(clock=sclk,MOSI=mosi,MISO=miso)
        except Exception as e:
            import bitbangio
            self.__spi=bitbangio.SPI(clock=sclk,MOSI=mosi,MISO=miso)
            
        self.__lock()
        self.__configure()
        self.__unlock()
        
    # Internal Stuff
    
    def __lock(self):
        while not self.__spi.try_lock():
            pass
        
    def __unlock(self):
        self.__spi.unlock()
    
    def __prepare(self):
        self.__lock()
        self.__configure()
        self.__cs.value=True
    
    def __finish(self):
        self.__cs.value=False
        self.__unlock()
    
    def __configure(self):
        self.__spi.configure(baudrate=100000,polarity=0,phase=1)
        
    def bcdtodec(self,byte):
        return (((byte>>4)&0x07)*10)+(byte&0x0f)
    
    def dectobcd(self,num):
        num = int(num)
        un = int(num/10)
        ln = num - (un*10)
        return ((int(un))*16)+(int(ln))
    
    def __writeOn(self):
        prior=self.__read(0x0f)
        self.__prepare()
        self.__spi.write(bytearray([0x8f,prior&0x04]))
        self.__finish()

    def __writeOff(self):
        prior=self.__read(0x0f)
        self.__prepare()
        self.__spi.write(bytearray([0x8f,prior|0x40]))
        self.__finish()
        
    def __write(self,loc,val):
        self.__writeOn()
        self.__prepare()
        self.__spi.write(bytearray([loc,val]))
        self.__finish()
        self.__writeOff()
    
    def __writeBuf(self,buf):
        self.__writeOn()
        self.__prepare()
        self.__spi.write(buf)
        self.__finish()
        self.__writeOff()
    
    def __read(self,loc=-1):
        self.__prepare()
        result = bytearray(19)
        self.__spi.readinto(result)
        self.__finish()
        if loc==-1:
            return result
        else:
            return result[loc+1]
    
    #All of these below are the abstractions
    
    #Actual time - hours, minutes, seconds
    
    def setTime(self,h,m,s,th=0,ap=0):
        if th:
            h = h if h<=12 else h-12
            ap = ap%2           
            h=self.dectobcd(h)|0x40|0x20*ap
        else:
            h=self.dectobcd(h)
        self.__writeBuf(bytearray([0x80,self.dectobcd(s),self.dectobcd(m),h]))
    
    def getTime(self):
        h = self.__read(0x02)
        if not h>>6&1:
            h=self.bcdtodec(h),0,0
        else:
            h=self.bcdtodec(h&-0x21&-0x41),1,h>>5&1
        m=self.bcdtodec(self.__read(0x01))
        s=self.bcdtodec(self.__read(0x00))
        return h[0],m,s,h[1],h[2]
    
    #Date - year, month, day
    
    def getDayFromDate(self,y,m,d): #Sun 1, Sat 7
        t=(0,3,2,5,0,3,5,1,4,6,2,4)
        y-=m<3
        return ((y+int(y/4)-int(y/100)+int(y/400)+t[m-1]+d)%7)+1
    
    
    def setDate(self,y,m,d):
        w=self.dectobcd(self.getDayFromDate(y,m,d))
        y=self.dectobcd(y%100)
        m=self.dectobcd(m)
        d=self.dectobcd(d)
        self.__writeBuf(bytearray([0x83,w,d,m,y]))
    
    def getDate(self):
        y=self.bcdtodec(self.__read(0x06))
        m=self.bcdtodec(self.__read(0x05))
        d=self.bcdtodec(self.__read(0x04))
        w=self.bcdtodec(self.__read(0x03))
        return y,m,d,w
    
    #Alarms
    
    def setAlarmTime(self,a,h,m,s,w,fh,fm,fs,fw,th=0,ap=0):
        add=0x87 if not a else 0x8B
        if th:
            h = h if h<=12 else h-12
            ap = ap%2           
            h=self.dectobcd(h)|0x40|0x20*ap|0x80*fh
        else:
            h=self.dectobcd(h)|0x80*fh
        s=self.dectobcd(s)|0x80*fs
        m=self.dectobcd(m)|0x80*fm
        w=self.dectobcd(w)|0x80*fw
        self.__writeBuf(bytearray([add,s,m,h,w]))
    
    def getAlarmTime(self,a):
        h=self.__read(0x09+(4*a))
        m=self.__read(0x08+(4*a))
        s=self.__read(0x07+(4*a))
        w=self.__read(0x0a+(4*a))
        return bin(h&-0x81&-0x41),bin(m&-0x81),bin(s&-0x81),bin(w&-0x81),h>>7&1,m>>7&1,s>>7&1,w>>7&1
    
    def enableAlarmInt(self,a):
        n=0x01 if not a else 0x02
        self.__write(0x8f,self.__read(0x0f)|n)
    
    def disableAlarmInt(self,a):
        n=-0x02 if not a else -0x03
        self.__write(0x8f,(self.__read(0x0f))&n)
        
    def getAlarmStatus(self,a):
        return self.__read(0x10)>>a&1
    
    #Trickle Charger
        
    def setChargerState(self,d,r):
        if not d:
            d=self.__read(0x11)&-0x09|0x04
        else:
            d=self.__read(0x11)&-0x05|0x08
        self.__write(0x91,d)            
        if not r:
            r=self.__read(0x11)&-0x03|0x01
        elif r==1:
            r=self.__read(0x11)&-0x02|0x02
        else:
            r=self.__read(0x11)|0x01|0x02
        self.__write(0x91,r)        
    
    def enableCharger(self):
        self.__write(0x91,self.__read(0x11)&-0x41&-0x11|0x80|0x20)

    def disableCharger(self):
        self.__write(0x91,self.__read(0x11)&-0x81&-0x21|0x40|0x10)
    
    #Misc
        
    def enableHzPin(self):
        self.__write(0x8f,0x04)
    
    def disableHzPin(self):
        self.__write(0x8f,0x00)

