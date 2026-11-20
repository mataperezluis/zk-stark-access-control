idf_component_register(SRCS "main.cpp" "display.cpp" "touch.cpp" "allocator.cpp"
    INCLUDE_DIRS "../include"
    REQUIRES esp_driver_usb_serial_jtag esp_timer esp_lcd_jd9853 esp_driver_spi
             esp_driver_gpio esp_driver_i2c esp_psram bootloader_support esp_hw_support)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
set(ACCESS_VERIFIER "${CMAKE_CURRENT_LIST_DIR}/../../target-xtensa/xtensa-esp32s3-none-elf/release/libaccess_zk_embedded.a")
if(NOT EXISTS "${ACCESS_VERIFIER}")
    message(FATAL_ERROR "Build the real Xtensa verifier first: python scripts/cargo_xtensa.py build -p access-zk-embedded --release --target xtensa-esp32s3-none-elf")
endif()
add_library(access_zk_rust STATIC IMPORTED)
set_target_properties(access_zk_rust PROPERTIES IMPORTED_LOCATION "${ACCESS_VERIFIER}")
target_link_libraries(${COMPONENT_LIB} PUBLIC access_zk_rust)

