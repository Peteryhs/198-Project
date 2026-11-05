#pragma once

class Accelerometer{
    public: 
        int xPin;
        int yPin;
        int zPin; 


    public:
        Accelerometer(int xPin, int yPin, int zPin){
            this-> xPin = xPin;
            this-> yPin = yPin;
            this-> zPin = zPin; 
        }
}; 