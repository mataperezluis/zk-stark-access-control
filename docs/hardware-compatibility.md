# Hardware and build evidence

| Item | Evidence / configuration |
| --- | --- |
| MCU | COM5 esptool ROM query: ESP32-S3 QFN56, rev 0.2 |
| PSRAM | ROM query: embedded 8 MB AP_3v3; firmware selects octal, 40 MHz |
| Flash | flash_id: manufacturer 0x20, device 0x4018, 16 MB, quad, 3.3 V |
| Original board profile | esp32-s3-devkitc-1; generic profile says 8 MB / no PSRAM |
| New project overrides | 16 MB flash, DIO, 3 MiB factory app partition; no OTA |
| LCD | Existing functional source: JD9853, 172 × 320, RGB565 |
| LCD pins | CLK 38, MOSI 39, CS 21, DC 45, RESET 40, BL 46; SPI2, 40 MHz |
| LCD orientation | inversion enabled, no panel mirror, X gap 34 |
| Touch reference | .reference/waveshare-touch-147.zip, ESP-IDF/01_factory |
| Touch controller | AXS5106, 0x63; SDA 42, SCL 41, INT 47, RESET 48 |
| USB | native USB Serial/JTAG, VID:PID 303a:1001; COM5 observed |
| ESP-IDF | installed 6.1.0, framework package 4.60100.0 |
| PlatformIO | Core 6.2.0, Espressif32 platform pinned 7.1.3 |
| CPU for measured firmware | 160 MHz in generated ESP-IDF sdkconfig; dynamic frequency scaling disabled |
| C/C++ toolchain | installed Xtensa GCC 15.2.0 |
| Rust host | installed cargo/rustc stable 1.94.0 |
| Rust Xtensa | project-local Espressif 1.97.0.0, compiler 1.97.0-nightly |
| Rust target | xtensa-esp32s3-none-elf, libcore/liballoc built from matching sources |
| Interop | no_std staticlib, C ABI, caller-owned byte slices, explicit PSRAM allocator |

The real target compiled and linked, rather than inferring Xtensa compatibility from ARM or
RISC-V results. zkmcu's MCU benchmark numbers were not copied into this device's results.
[Espressif toolchain requirements](https://docs.espressif.com/projects/rust/book/getting-started/toolchain.html).

The JD9853 driver and bitmap font are copied inside the independent firmware. Touch's small
polling implementation reproduces the reference's register protocol; it probes 0x63 and does
not invent extra hardware. Orientation comes from the reference rotation-0 profile. Physical
touch coordinate alignment and screen readability need human visual confirmation even when
I2C probing and LCD transfers succeed.

No NVS credentials are provisioned on the board. The device holds only the public root/epoch.
Before deployment the entire previous flash was read into a private local backup. No erase-all,
security-enable command, eFuse burn or JTAG security command is part of this project.

