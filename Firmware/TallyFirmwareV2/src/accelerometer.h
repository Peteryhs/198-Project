#ifndef ACCELEROMETER_H
#define ACCELEROMETER_H

#include <stdint.h>

#include "esp_adc/adc_oneshot.h"

// Attenuation of all six channels, reported in HELLO as the raw adc_atten_t value (3 = 12 dB).
#define ACCELEROMETER_ATTEN ADC_ATTEN_DB_12

void accelerometer_init(void);
// Reads all six channels in contract order (GPIO36/39/34 upper x/y/z, GPIO35/32/33 forearm x/y/z)
// and converts each with the line-fitting calibration. Millivolts, unfiltered.
void accelerometer_read_mv(uint16_t mv[6]);

#endif
