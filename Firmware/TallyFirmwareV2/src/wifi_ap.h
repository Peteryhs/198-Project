#ifndef WIFI_AP_H
#define WIFI_AP_H

#include <stdint.h>

// Starts the WPA2 SoftAP and writes the SoftAP MAC (the one in the SSID and in HELLO) to mac.
void wifi_ap_start(uint8_t mac[6]);

#endif
