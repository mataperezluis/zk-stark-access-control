The LCD component is copied under ../components/esp_lcd_jd9853.
The real verifier is built as a no_std Rust static library inside this isolated project;
see src/CMakeLists.txt and ../../verifier/embedded. No original-project library is linked.

