Driver adapted from the official Waveshare demo:
https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-1.47/ESP32-S3-Touch-LCD-1.47-Demo.zip

Original directory: ESP-IDF/03_lvgl_example/components/esp_lcd_jd9853
Source files retain their Apache-2.0 SPDX license notices.

Compatibility change for ESP-IDF 6: replace the removed rgb_endian field and
LCD_RGB_ENDIAN_* aliases with rgb_ele_order and LCD_RGB_ELEMENT_ORDER_*.

Board wiring and initialization follow esp_bsp/bsp_display.c and bsp_display.h
from that example. This is a provisional hardware match based on the user's
description, not a confirmed identification. Touch is not initialized in this test.
