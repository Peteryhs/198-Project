#include "accelerometer_reading.h" 
#include <Arduino.h>

Accelerometer::Accelerometer(int xPin, int yPin, int zPin){
    this-> xPin = xPin;
    this-> yPin = yPin; 
    this-> zPin = zPin; 
}

Accelerometer::readX(){
    return analogRead(xPin);
}
Accelerometer::readY(){
    return analogRead(yPin);
}
Accelerometer::readZ(){
    return analogRead(zPin);
}

Accelerometer::convertX(){
    return (readX() - 512) * 0.0039; 
}
Accelerometer::convertY(){
    return (readY() - 512) * 0.0039; 
}
Accelerometer::convertZ(){
    return (readZ() - 512) * 0.0039; 
}
