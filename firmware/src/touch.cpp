// AXS5106 register layout and pins from Waveshare's supplied 1.47-inch demo.
// Original touch header: SPDX-FileCopyrightText: 2022 Espressif Systems (Shanghai) CO LTD
// SPDX-License-Identifier: Apache-2.0
#include "touch.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
namespace {
i2c_master_bus_handle_t bus=nullptr;
i2c_master_dev_handle_t device=nullptr;
}
bool touch_start() {
    if(gpio_set_direction(GPIO_NUM_48, GPIO_MODE_OUTPUT)!=ESP_OK) return false;
    gpio_set_level(GPIO_NUM_48,0); vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(GPIO_NUM_48,1); vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_direction(GPIO_NUM_47,GPIO_MODE_INPUT);
    i2c_master_bus_config_t cfg{};
    cfg.i2c_port=I2C_NUM_0; cfg.sda_io_num=GPIO_NUM_42; cfg.scl_io_num=GPIO_NUM_41;
    cfg.clk_source=I2C_CLK_SRC_DEFAULT; cfg.glitch_ignore_cnt=7;
    cfg.flags.enable_internal_pullup=true;
    if(i2c_new_master_bus(&cfg,&bus)!=ESP_OK) return false;
    if(i2c_master_probe(bus,0x63,100)!=ESP_OK) return false;
    i2c_device_config_t dev{}; dev.dev_addr_length=I2C_ADDR_BIT_LEN_7;
    dev.device_address=0x63; dev.scl_speed_hz=400000;
    return i2c_master_bus_add_device(bus,&dev,&device)==ESP_OK;
}
bool touch_read(std::uint16_t &x,std::uint16_t &y) {
    if(!device) return false;
    std::uint8_t reg=1, data[14]{};
    if(i2c_master_transmit(device,&reg,1,30)!=ESP_OK ||
       i2c_master_receive(device,data,sizeof(data),30)!=ESP_OK) return false;
    if((data[1]&15)==0) return false;
    const auto raw_x=static_cast<std::uint16_t>(((data[2]&15)<<8)|data[3]);
    const auto raw_y=static_cast<std::uint16_t>(((data[4]&15)<<8)|data[5]);
    if(raw_x>=172 || raw_y>=320) return false;
    x=171-raw_x; y=raw_y; // Waveshare rotation-0 profile mirrors X.
    return true;
}

