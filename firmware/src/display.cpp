#include "display.h"
#include "display_font.h"
#include "touch.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_heap_caps.h"
#include "esp_lcd_jd9853.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <atomic>
#include <cstdio>
#include <cstring>
namespace access_ui {
namespace {
constexpr int width=172,height=320,rows=16;
constexpr std::uint16_t background=0x0863,card=0x10e5,white=0xffff,muted=0x8c92,cyan=0x07ff,green=0x4f54,red=0xf9c7;
Snapshot state;
portMUX_TYPE state_lock=portMUX_INITIALIZER_UNLOCKED;
std::atomic<std::uint32_t> selected{1}, frames{0};
std::atomic<bool> working{false};
std::atomic<bool> touch_working{false};
std::atomic<std::uint32_t> last_render{0};
esp_lcd_panel_io_handle_t io=nullptr;
esp_lcd_panel_handle_t panel=nullptr;
SemaphoreHandle_t transferred=nullptr;
std::uint16_t *pixels=nullptr;
struct Text { char value[32];int x,y,scale;std::uint16_t color; };
Text text[28];int count=0;
void add(const char *value,int x,int y,int scale,std::uint16_t color) {
    if(count>=28)return;
    auto &t=text[count++];std::snprintf(t.value,sizeof(t.value),"%s",value);
    t.x=x;t.y=y;t.scale=scale;t.color=color;
}
void centered(const char *value,int y,int scale,std::uint16_t color) {
    add(value,(width-(int(std::strlen(value))*6-1)*scale)/2,y,scale,color);
}
bool text_pixel(const Text &t,int x,int y) {
    if(x<t.x || y<t.y || y>=t.y+7*t.scale)return false;
    const int col=(x-t.x)/t.scale;
    if(col/6>=int(std::strlen(t.value)) || col%6==5)return false;
    const char *glyph=std::strchr(letters,t.value[col/6]);
    return glyph && (font[glyph-letters][col%6]&(1U<<((y-t.y)/t.scale)));
}
void layout(const Snapshot &s) {
    count=0;
    centered("ZK-STARK",9,2,white);centered("ACCESS CONTROL",30,1,muted);
    const char *label="SYSTEM READY";auto accent=cyan;
    switch(s.stage){
    case Stage::ready:break;
    case Stage::waiting:label="WAITING FOR REQUEST";break;
    case Stage::challenge:label="CHALLENGE GENERATED";break;
    case Stage::receiving:label="RECEIVING PROOF";break;
    case Stage::verifying:label="VERIFYING STARK";break;
    case Stage::granted:label="ACCESS GRANTED";accent=green;break;
    case Stage::denied:label="ACCESS DENIED";accent=red;break;
    case Stage::expired:label="AUTHORIZATION EXPIRED";accent=red;break;
    }
    centered(label,51,1,accent);
    centered(s.checked?(s.valid?"PROOF VALID":"PROOF INVALID"):"NO PROOF VERIFIED",69,1,s.valid?green:muted);
    char value[32];
    std::snprintf(value,sizeof(value),"OP %lu / SELECT %lu",(unsigned long)s.operation,(unsigned long)selected.load());
    add(value,10,91,1,white);
    std::snprintf(value,sizeof(value),"PROOF %lu BYTES",(unsigned long)s.proof_bytes);add(value,10,110,1,white);
    std::snprintf(value,sizeof(value),"VERIFY %.2f MS",s.verify_us/1000.0);add(value,10,128,1,cyan);
    std::snprintf(value,sizeof(value),"FREE %lu KB",(unsigned long)(heap_caps_get_free_size(MALLOC_CAP_8BIT)/1024));add(value,10,146,1,white);
    std::snprintf(value,sizeof(value),"MIN  %lu KB",(unsigned long)(heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT)/1024));add(value,10,162,1,muted);
    std::snprintf(value,sizeof(value),"OK %lu / BAD %lu",(unsigned long)s.successes,(unsigned long)s.rejected);add(value,10,180,1,white);
    centered(s.maintenance?"MAINTENANCE ACTIVE":"ACCESS RESTRICTED",200,1,s.maintenance?green:muted);
    const char *names[]={"DIAGNOSTICS","ENTER MAINTENANCE","SET CONFIGURATION","EXIT MAINTENANCE"};
    for(int i=0;i<4;++i){
        std::snprintf(value,sizeof(value),"%lu %s",(unsigned long)(i+1),names[i]);
        add(value,12,222+i*20,1,selected.load()==std::uint32_t(i+1)?cyan:muted);
    }
    centered("SELECT THEN PROVE VIA USB",307,1,white);
}
bool done(esp_lcd_panel_io_handle_t,esp_lcd_panel_io_event_data_t *,void *) {
    BaseType_t awakened=pdFALSE;xSemaphoreGiveFromISR(transferred,&awakened);return awakened==pdTRUE;
}
bool render(const Snapshot &s) {
    layout(s);
    for(int top=0;top<height;top+=rows){
        for(int row=0;row<rows;++row)for(int x=0;x<width;++x){
            const int y=top+row;
            std::uint16_t color=(y>=44&&y<83)||(y>=217&&y<298)?card:background;
            for(int i=0;i<count;++i)if(text_pixel(text[i],x,y)){color=text[i].color;break;}
            pixels[row*width+x]=std::uint16_t((color>>8)|(color<<8));
        }
        if(esp_lcd_panel_draw_bitmap(panel,0,top,width,top+rows,pixels)!=ESP_OK ||
           xSemaphoreTake(transferred,pdMS_TO_TICKS(2000))!=pdTRUE)return false;
    }
    gpio_set_level(GPIO_NUM_46,1);++frames;return true;
}
bool init_panel() {
    if(gpio_reset_pin(GPIO_NUM_46)!=ESP_OK || gpio_set_direction(GPIO_NUM_46,GPIO_MODE_OUTPUT)!=ESP_OK)return false;
    gpio_set_level(GPIO_NUM_46,0);
    spi_bus_config_t bus{};bus.sclk_io_num=38;bus.mosi_io_num=39;bus.miso_io_num=-1;
    bus.quadwp_io_num=-1;bus.quadhd_io_num=-1;bus.max_transfer_sz=width*rows*2;
    if(spi_bus_initialize(SPI2_HOST,&bus,SPI_DMA_CH_AUTO)!=ESP_OK)return false;
    esp_lcd_panel_io_spi_config_t cfg{};cfg.cs_gpio_num=GPIO_NUM_21;cfg.dc_gpio_num=GPIO_NUM_45;
    cfg.spi_mode=0;cfg.pclk_hz=40000000;cfg.trans_queue_depth=1;cfg.on_color_trans_done=done;
    cfg.lcd_cmd_bits=8;cfg.lcd_param_bits=8;
    if(esp_lcd_new_panel_io_spi(static_cast<esp_lcd_spi_bus_handle_t>(SPI2_HOST),&cfg,&io)!=ESP_OK)return false;
    esp_lcd_panel_dev_config_t dev{};dev.reset_gpio_num=GPIO_NUM_40;
    dev.rgb_ele_order=LCD_RGB_ELEMENT_ORDER_RGB;dev.bits_per_pixel=16;
    return esp_lcd_new_panel_jd9853(io,&dev,&panel)==ESP_OK &&
        esp_lcd_panel_reset(panel)==ESP_OK && esp_lcd_panel_init(panel)==ESP_OK &&
        esp_lcd_panel_invert_color(panel,true)==ESP_OK && esp_lcd_panel_mirror(panel,false,false)==ESP_OK &&
        esp_lcd_panel_set_gap(panel,34,0)==ESP_OK && esp_lcd_panel_disp_on_off(panel,true)==ESP_OK;
}
void task(void *) {
    const bool touch=touch_start();
    touch_working=touch;
    bool pressed=false;
    for(;;){
        std::uint16_t x=0,y=0;const bool down=touch&&touch_read(x,y);
        if(down&&!pressed && y>=215&&y<295)selected=1+(y-215)/20;
        pressed=down;
        Snapshot s;portENTER_CRITICAL(&state_lock);s=state;portEXIT_CRITICAL(&state_lock);
        const auto started=esp_timer_get_time();
        if(!render(s)){working=false;gpio_set_level(GPIO_NUM_46,0);vTaskDelete(nullptr);}
        last_render=static_cast<std::uint32_t>(esp_timer_get_time()-started);
        vTaskDelay(pdMS_TO_TICKS(150));
    }
}
}
bool start() {
    transferred=xSemaphoreCreateBinary();
    pixels=static_cast<std::uint16_t *>(heap_caps_malloc(width*rows*2,MALLOC_CAP_DMA|MALLOC_CAP_INTERNAL));
    if(!transferred||!pixels||!init_panel())return false;
    working=true;
    if(xTaskCreatePinnedToCore(task,"security_lcd",6144,nullptr,1,nullptr,1)!=pdPASS){working=false;return false;}
    return true;
}
void update(const Snapshot &s){portENTER_CRITICAL(&state_lock);state=s;portEXIT_CRITICAL(&state_lock);}
std::uint32_t selected_operation(){return selected.load();}
bool healthy(){return working.load();}
std::uint32_t frames_rendered(){return frames.load();}
bool touch_healthy(){return touch_working.load();}
std::uint32_t render_us(){return last_render.load();}
}

