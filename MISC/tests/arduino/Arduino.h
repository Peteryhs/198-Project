#ifndef TEST_ARDUINO_H
#define TEST_ARDUINO_H
#include <stdint.h>
#include <string>
#include <sstream>
struct HardwareSerial {
    std::string input, output;
    unsigned cursor = 0;
    void begin(unsigned long) {}
    int available() { return cursor < input.size(); }
    int read() { return (unsigned char)input[cursor++]; }
    template<class T> void print(T value) { std::ostringstream s; s << value; output += s.str(); }
    void print(float value, int) { print(value); }
    void println() { output += '\n'; }
    template<class T> void println(T value) { print(value); println(); }
    void println(float value, int n) { print(value, n); println(); }
};
extern HardwareSerial Serial;
#endif
