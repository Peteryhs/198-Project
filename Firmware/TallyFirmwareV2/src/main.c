#include <stdint.h>

#include "accelerometer.h"
#include "link_server.h"
#include "sampler.h"
#include "wifi_ap.h"

// One job per module: accelerometer reads millivolts, sampler owns the 100 Hz tick and the set,
// wifi_ap brings up the WPA2 SoftAP, link_server speaks ESP32-WIRE-V1 over TCP.
void app_main(void)
{
    uint8_t mac[6];
    accelerometer_init();
    wifi_ap_start(mac);
    sampler_start();
    link_server_start(mac);
}
