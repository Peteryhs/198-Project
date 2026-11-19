# This file was automatically generated for projects
# without default 'CMakeLists.txt' file.

FILE(GLOB_RECURSE app_sources "${CMAKE_SOURCE_DIR}/src/*.c")

idf_component_register(
    SRCS ${app_sources}
    REQUIRES esp_adc esp_event esp_netif esp_timer esp_wifi lwip nvs_flash
)
