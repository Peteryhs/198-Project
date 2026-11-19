#include "wifi_ap.h"

#include <stdio.h>
#include <string.h>

#include "esp_err.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

// The one WPA2 credential every Tally board ships with (8..63 printable ASCII).
// The owner chooses the real value; the phone user types it into the Connect screen.
#define TALLY_AP_PASSPHRASE "tally-link-v1"
#define TALLY_AP_CHANNEL 1
// esp_wifi_set_max_tx_power units are 0.25 dBm: 34 = 8.5 dBm. The phone is within about 1 m;
// lower TX power lowers current peaks, which cause brownouts (ESP32-WIRE-V1 obligation 5).
#define TALLY_AP_MAX_TX_POWER 34

static const char *TAG = "WIFI_AP";

void wifi_ap_start(uint8_t mac[6])
{
    esp_err_t nvs = nvs_flash_init();
    if (nvs == ESP_ERR_NVS_NO_FREE_PAGES || nvs == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvs = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvs);
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_ap(); // 192.168.4.1/24, DHCP server on, gateway 192.168.4.1

    const wifi_init_config_t wifi_init_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wifi_init_config));
    ESP_ERROR_CHECK(esp_read_mac(mac, ESP_MAC_WIFI_SOFTAP));

    wifi_config_t ap_config = {
        .ap = {
            .channel = TALLY_AP_CHANNEL,
            .max_connection = 1,
            .authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    // Contract §2: Tally-<last two MAC bytes, uppercase hex>, from the same MAC HELLO reports.
    int ssid_len = snprintf((char *)ap_config.ap.ssid, sizeof(ap_config.ap.ssid), "Tally-%02X%02X", mac[4], mac[5]);
    ap_config.ap.ssid_len = (uint8_t)ssid_len;
    _Static_assert(sizeof(TALLY_AP_PASSPHRASE) - 1 >= 8 && sizeof(TALLY_AP_PASSPHRASE) - 1 <= 63,
                   "WPA2 passphrase must be 8..63 characters");
    memcpy(ap_config.ap.password, TALLY_AP_PASSPHRASE, sizeof(TALLY_AP_PASSPHRASE));

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_max_tx_power(TALLY_AP_MAX_TX_POWER));

    ESP_LOGI(TAG, "WPA2 AP '%s' on channel %d at 192.168.4.1", (const char *)ap_config.ap.ssid, TALLY_AP_CHANNEL);
}
