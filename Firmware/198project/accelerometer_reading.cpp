#include "accelerometer_reading.h" 
#include <Arduino.h>

Accelerometer::Accelerometer(int xPin, int yPin, int zPin){
    this->xPin = xPin;
    this->yPin = yPin; 
    this->zPin = zPin; 
}

int Accelerometer::readX(){
    return analogRead(xPin);
}
int Accelerometer::readY(){
    return analogRead(yPin);
}
int Accelerometer::readZ(){
    return analogRead(zPin);
}

// Fixed conversion functions for a 5V Arduino reading an ADXL335
float Accelerometer::convertX(){
    return (readX() - 338) * 0.0148; 
}
float Accelerometer::convertY(){
    return (readY() - 338) * 0.0148; 
}
float Accelerometer::convertZ(){
    return (readZ() - 338) * 0.0148; 
}
