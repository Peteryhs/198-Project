#include "accelerometer_reading.h"
#include <Arduino.h>


//pin out
constexpr int XPIN1 =0;
constexpr int YPIN1 =1;
constexpr int ZPIN1 =2;

constexpr int XPIN2 =3;
constexpr int YPIN2 =4; 
constexpr int ZPIN2 =5;

constexpr int OFF_BUTTON_PIN = 2; 
constexpr int COLLECT_BUTTON_PIN = 3; 


//variables
volatile bool serverOn = false;
volatile bool collectData = false;


Accelerometer accelerometer1(XPIN1, YPIN1, ZPIN1);
Accelerometer accelerometer2(XPIN2, YPIN2, ZPIN2);

void offButtonPress(){
    if(serverOn){
        serverOn = false;
        Serial.println("Server turned off.");
    } else {
        serverOn = true;
        Serial.println("Server turned on.");
    }
}

void collectButtonPress(){
    if(serverOn&& !collectData){
        collectData = true;
    }
    else if (serverOn && collectData){
        collectData = false;
    }
    else{
        return;
    }
}

void sendData(float x1, float y1, float z1, float x2, float y2, float z2){


}

void setup(){
    Serial.begin(9600);

    attachInterrupt(digitalPinToInterrupt(OFF_BUTTON_PIN), offButtonPress, FALLING);
    attachInterrupt(digitalPinToInterrupt(COLLECT_BUTTON_PIN), collectButtonPress, FALLING);
}
void loop(){
    if(serverOn && collectData){
        float x1 = accelerometer1.convertX();
        float y1 = accelerometer1.convertY();
        float z1 = accelerometer1.convertZ();

        float x2 = accelerometer2.convertX();
        float y2 = accelerometer2.convertY();
        float z2 = accelerometer2.convertZ();

        sendData(x1, y1, z1, x2, y2, z2);
    }
}