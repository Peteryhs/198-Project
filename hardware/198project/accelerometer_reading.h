#pragma once

class Accelerometer{
    private: 
        int xPin;
        int yPin;
        int zPin; 


    public:
        Accelerometer(int xPin, int yPin, int zPin);

        int readX();
        int readY();
        int readZ();

        float convertX();
        float convertY();
        float convertZ();
}; 