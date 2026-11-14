#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string>
#include <deque>
#include <cmath>
struct __FlashStringHelper {};
#define F(x) reinterpret_cast<const __FlashStringHelper *>(x)
#define A0 0
#define A1 1
#define A2 2
#define A3 3
#define A4 4
#define A5 5
class FakeSerial {
public:
  std::string out;
  std::deque<char> in;
  void begin(unsigned long) {}
  int available() { return (int)in.size(); }
  int read() { char c=in.front(); in.pop_front(); return c; }
  void inject(const char *s) { while (*s) in.push_back(*s++); }
  void print(const char *s) { out += s; }
  void print(const __FlashStringHelper *s) { out += reinterpret_cast<const char *>(s); }
  void print(char c) { out += c; }
  void print(unsigned long n) { out += std::to_string(n); }
  void print(int n) { out += std::to_string(n); }
  void print(float x, int digits) { char b[64]; snprintf(b,sizeof b,"%.*f",digits,(double)x); out += b; }
  void println() { out += '\n'; }
  void println(char c) { out += c; out += '\n'; }
  void println(const char *s) { out += s; out += '\n'; }
  void println(const __FlashStringHelper *s) { out += reinterpret_cast<const char *>(s); out += '\n'; }
  void clear() { out.clear(); }
};
extern FakeSerial Serial;
extern FakeSerial Serial1;
inline unsigned long &fakeClock() { static unsigned long us=0; return us; }
inline unsigned long micros() { return fakeClock(); }
inline unsigned long millis() { return fakeClock()/1000; }
inline int analogRead(int) { return 338; }
