#include "accelerometer.h"

#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"
#include "esp_log.h"

static const char *TAG = "ADC";
static adc_oneshot_unit_handle_t adc1_handle;
static adc_cali_handle_t adc1_cali_handle;

static const int accelerometer_pins[6] = {36, 39, 34, 35, 32, 33};
static const adc_channel_t accelerometer_channels[6] = {
    ADC_CHANNEL_0, // GPIO36 (VP)
    ADC_CHANNEL_3, // GPIO39 (VN)
    ADC_CHANNEL_6, // GPIO34
    ADC_CHANNEL_7, // GPIO35
    ADC_CHANNEL_4, // GPIO32
    ADC_CHANNEL_5, // GPIO33
};

void accelerometer_init(void)
{
    const adc_oneshot_unit_init_cfg_t unit_config = {
        .unit_id = ADC_UNIT_1,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit_config, &adc1_handle));

    const adc_cali_line_fitting_config_t calibration_config = {
        .unit_id = ADC_UNIT_1,
        .atten = ACCELEROMETER_ATTEN,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .default_vref = 1100,
    };
    ESP_ERROR_CHECK(adc_cali_create_scheme_line_fitting(
        &calibration_config, &adc1_cali_handle));

    const adc_oneshot_chan_cfg_t channel_config = {
        .atten = ACCELEROMETER_ATTEN,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };

    for (int i = 0; i < 6; i++) {
        ESP_LOGI(TAG, "Configuring GPIO%d as ADC1 channel %d",
                 accelerometer_pins[i], accelerometer_channels[i]);
        ESP_ERROR_CHECK(adc_oneshot_config_channel(
            adc1_handle, accelerometer_channels[i], &channel_config));
    }
}

void accelerometer_read_mv(uint16_t mv[6])
{
    for (int i = 0; i < 6; i++) {
        int raw = 0;
        int voltage_mv = 0;
        ESP_ERROR_CHECK(adc_oneshot_read(adc1_handle, accelerometer_channels[i], &raw));
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(adc1_cali_handle, raw, &voltage_mv));
        mv[i] = (uint16_t)(voltage_mv < 0 ? 0 : voltage_mv);
    }
}
