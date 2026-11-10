#include "accelerometer_reading.h"
#include "data_transfer.h"
#include <Arduino.h>




Accelerometer accelerometer1(0,1,2);
Accelerometer accelerometer2(3,4,5);
void setup(){
    Serial.begin(9600);
}
void loop(){
     // Read and convert values for the first accelerometer
    float x1 = accelerometer1.convertX();
    float y1 = accelerometer1.convertY();
    float z1 = accelerometer1.convertZ();

    // Read and convert values for the second accelerometer
    float x2 = accelerometer2.convertX();
    float y2 = accelerometer2.convertY();
    float z2 = accelerometer2.convertZ();

    // Print Sensor 1 readings
    Serial.print("[Sensor 1] X: "); Serial.print(x1, 2); Serial.print("g  Y: "); Serial.print(y1, 2); Serial.print("g  Z: "); Serial.print(z1, 2); Serial.print("g | ");
    
    // Print Sensor 2 readings
    Serial.print("[Sensor 2] X: "); Serial.print(x2, 2); Serial.print("g  Y: "); Serial.print(y2, 2); Serial.print("g  Z: "); Serial.print(z2, 2); Serial.println("g");

    delay(200); // Small delay to make the serial monitor readable
}