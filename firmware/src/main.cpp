#include "access_zk.h"
#include "display.h"
#include "driver/usb_serial_jtag.h"
#include "esp_heap_caps.h"
#include "esp_mac.h"
#include "esp_psram.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "bootloader_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#if __has_include("policy_generated.h")
#include "policy_generated.h"
#else
#define ACCESS_POLICY_CONFIGURED 0
#define ACCESS_POLICY_EPOCH 0
static const std::uint8_t ACCESS_POLICY_ROOT[24]={};
#endif
extern "C" std::size_t access_peak();
extern "C" void access_reset_peak();
namespace {
constexpr std::uint32_t max_proof=524288, ttl_ms=60000, lease_ms=30000;
constexpr std::size_t max_payload=1024;
constexpr std::uint8_t magic[]={ 'Z','K','A','C' };
constexpr char policy_id[]="ZK-P3-ACCESS-V1!";
enum Code : std::uint32_t { ok=0, invalid=1, expired=2, replay=3, framing=4,
                            busy=5, unavailable=6, policy=7, operation_error=8, memory=9 };
enum Type : std::uint8_t { hello=1, request=2, begin=3, chunk=4, finish=5, abort_request=6, status=7, direct=8 };
std::uint8_t header[12]{}, payload[max_payload+4]{}, context[128]{}, public_inputs[120]{};
std::size_t header_used=0, payload_used=0, expected=0, received=0, proof_length=0;
std::uint8_t *proof=nullptr;
std::uint32_t active_id=0, consumed_id=0, op=0, argument=0, config_value=25;
std::int64_t frame_started=0, frame_last=0, deadline=0, requested_at=0, transfer_started=0, last_chunk=0, maintenance_deadline=0, result_until=0;
std::uint32_t verify_us=0, transfer_us=0, total_us=0, successes=0, rejects=0;
bool pending=false, receiving=false, maintenance=false, valid=false, ready=false, checked=false, proof_valid=false;
access_ui::Stage stage=access_ui::Stage::ready;
std::uint32_t u32(const std::uint8_t *p) { return std::uint32_t(p[0])|(std::uint32_t(p[1])<<8)|(std::uint32_t(p[2])<<16)|(std::uint32_t(p[3])<<24); }
void put(std::uint8_t *p,std::uint32_t n) { for(int i=0;i<4;++i)p[i]=static_cast<std::uint8_t>(n>>(8*i)); }
std::uint32_t crc(const std::uint8_t *p,std::size_t size,std::uint32_t value=0) {
    value=~value;
    for(std::size_t i=0;i<size;++i){value^=p[i];for(int b=0;b<8;++b)value=(value>>1)^(0xedb88320U&-(value&1U));}
    return ~value;
}
bool write(const std::uint8_t *data,std::size_t length) {
    while(length){int n=usb_serial_jtag_write_bytes(data,length,pdMS_TO_TICKS(1000));if(n<=0)return false;data+=n;length-=n;} return true;
}
void send(std::uint8_t type,std::uint32_t id,const std::uint8_t *data,std::size_t length) {
    std::uint8_t h[12]{}; std::memcpy(h,magic,4); h[4]=1;h[5]=type|0x80;
    h[6]=length&255;h[7]=(length>>8)&255;put(h+8,id);
    std::uint8_t tail[4];put(tail,crc(data,length,crc(h,sizeof(h))));
    write(h,sizeof(h));write(data,length);write(tail,sizeof(tail));
}
void publish() {
    access_ui::Snapshot s; s.stage=stage;s.proof_bytes=proof_length;s.verify_us=verify_us;
    s.heap=heap_caps_get_free_size(MALLOC_CAP_8BIT);s.min_heap=heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT);
    s.successes=successes;s.rejected=rejects;s.operation=op;s.config=config_value;
    s.maintenance=maintenance;s.valid=proof_valid;s.checked=checked;
    access_ui::update(s);
}
void release() {
    heap_caps_free(proof);proof=nullptr;receiving=false;received=0;
}
void consume() {
    if(pending)consumed_id=active_id;
    pending=false;deadline=0;
}
void lock() { maintenance=false;maintenance_deadline=0;valid=false; }
void deny() { consume();release();lock();checked=false;proof_valid=false;++rejects;stage=access_ui::Stage::denied;publish(); }
void result(std::uint8_t type,std::uint32_t id,Code code,bool accepted=false) {
    std::uint8_t out[88]{};
    std::uint32_t fields[]={code,op,accepted?config_value:0U,maintenance?1U:0U,accepted?1U:0U,
        successes,rejects,static_cast<std::uint32_t>(proof_length),verify_us,
        static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_8BIT)),
        static_cast<std::uint32_t>(heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT)),
        static_cast<std::uint32_t>(access_peak()),static_cast<std::uint32_t>(uxTaskGetStackHighWaterMark(nullptr)),
        transfer_us,total_us,access_ui::selected_operation(),
        access_ui::healthy()?1U:0U,access_ui::frames_rendered(),
        static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)),
        static_cast<std::uint32_t>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),
        access_ui::touch_healthy()?1U:0U,access_ui::render_us()};
    for(std::size_t i=0;i<22;++i)put(out+i*4,fields[i]);
    send(type,id,out,sizeof(out));
}
void fail(std::uint8_t type,std::uint32_t id,Code code,bool crypto_checked=false,bool crypto_valid=false) {
    deny();checked=crypto_checked;proof_valid=crypto_valid;publish();result(type,id,code);
}
void poll(std::int64_t now) {
    if(valid && !maintenance && now>=result_until){valid=false;stage=access_ui::Stage::waiting;publish();}
    if(maintenance && now>=maintenance_deadline){lock();stage=access_ui::Stage::expired;publish();}
    if(pending && (now>=deadline || (receiving && now-last_chunk>3000000))){
        const auto id=active_id;deny();stage=access_ui::Stage::expired;publish();result(finish,id,expired);
    }
}
bool operation_allowed(std::uint32_t value,std::uint32_t arg) {
    return value>=1 && value<=4 && (value==3?arg<=100:arg==0);
}
void handle(std::uint8_t type,std::uint32_t id,const std::uint8_t *data,std::size_t length) {
    const auto now=esp_timer_get_time();poll(now);
    if(type==hello && length==0){
        std::uint8_t out[28]{};put(out,1);put(out+4,max_proof);put(out+8,max_payload-4);
        put(out+12,ttl_ms);put(out+16,lease_ms);put(out+20,ready?1:0);put(out+24,ACCESS_POLICY_EPOCH);
        send(type,id,out,sizeof(out));return;
    }
    if(type==status && length==0){result(type,id,ok);return;}
    if(type==direct){fail(type,id,operation_error);return;}
    if(type==abort_request && length==0){deny();result(type,id,ok);return;}
    if(type==request){
        if(!ready || !access_ui::healthy()){fail(type,id,unavailable);return;}
        if(length!=8 || id==0 || !operation_allowed(u32(data),u32(data+4))){fail(type,id,operation_error);return;}
        if(id==consumed_id || (pending && id==active_id)){fail(type,id,replay);return;}
        consume();release();valid=false;checked=false;proof_valid=false;
        op=u32(data);argument=u32(data+4);
        if(op==3 && !maintenance){fail(type,id,operation_error);return;}
        active_id=id;pending=true;requested_at=now;deadline=now+ttl_ms*1000LL;
        proof_length=0;verify_us=0;transfer_us=0;total_us=0;
        std::memset(context,0,32);std::memcpy(context,ACCESS_POLICY_ROOT,24);
        bootloader_random_enable();esp_fill_random(context+32,32);bootloader_random_disable();
        put(context+96,ACCESS_POLICY_EPOCH);put(context+100,id);put(context+104,op);put(context+108,argument);
        std::memcpy(context+112,policy_id,16);
        std::uint8_t out[132];std::memcpy(out,context,128);put(out+128,ttl_ms);
        stage=access_ui::Stage::challenge;publish();send(type,id,out,sizeof(out));return;
    }
    if(!pending || id!=active_id){fail(type,id,replay);return;}
    if(now>=deadline){fail(type,id,expired);return;}
    if(type==begin){
        if(receiving || length!=124){fail(type,id,framing);return;}
        const auto size=u32(data);
        if(size==0 || size>max_proof){fail(type,id,memory);return;}
        proof=static_cast<std::uint8_t *>(heap_caps_malloc(size,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
        if(!proof){fail(type,id,memory);return;}
        std::memcpy(public_inputs,data+4,120);proof_length=size;received=0;
        receiving=true;transfer_started=now;last_chunk=now;stage=access_ui::Stage::receiving;publish();
    } else if(type==chunk){
        if(!receiving || length<=4 || u32(data)!=received || length-4>proof_length-received){fail(type,id,framing);return;}
        std::memcpy(proof+received,data+4,length-4);received+=length-4;last_chunk=now;
    } else if(type==finish){
        if(length || !receiving || received!=proof_length){fail(type,id,framing);return;}
        // Consume before crypto; success, failure, reboot, timeout and replay all spend this nonce.
        consume();valid=false;stage=access_ui::Stage::verifying;publish();
        transfer_us=static_cast<std::uint32_t>(now-transfer_started);
        access_reset_peak();const auto started=esp_timer_get_time();
        const int verdict=access_zk_verify(proof,proof_length,public_inputs,120,context,128);
        const auto ended=esp_timer_get_time();verify_us=static_cast<std::uint32_t>(ended-started);
        release();
        // Expiry and maintenance preconditions are checked again after the blocking verifier.
        if(verdict!=0 || ended-requested_at>=ttl_ms*1000LL){fail(type,id,verdict?invalid:expired,true,verdict==0);return;}
        if(!access_ui::healthy()){fail(type,id,unavailable,true,true);return;}
        if(op==3 && (!maintenance || ended>=maintenance_deadline)){fail(type,id,operation_error,true,true);return;}
        checked=true;proof_valid=true;valid=true;result_until=ended+2000000;++successes;
        switch(op){
        case 1: break; // Protected diagnostics returned only in this accepted result.
        case 2: maintenance=true;maintenance_deadline=ended+lease_ms*1000LL;break;
        case 3: config_value=argument;break; // Actual noncritical RAM configuration.
        case 4: maintenance=false;maintenance_deadline=0;break;
        default: fail(type,id,operation_error);return;
        }
        total_us=static_cast<std::uint32_t>(ended-requested_at);
        stage=access_ui::Stage::granted;publish();result(type,id,ok,true);return;
    } else {fail(type,id,framing);return;}
    std::uint8_t ack[8]{};put(ack+4,received);send(type,id,ack,sizeof(ack));
}
void reset_frame(){header_used=0;payload_used=0;expected=0;frame_started=0;}
void feed(std::uint8_t byte,std::int64_t now) {
    if(header_used<4){
        if(byte==magic[header_used]){if(header_used==0)frame_started=now;header[header_used++]=byte;}
        else header_used=(byte==magic[0])?1:0;
        frame_last=now;return;
    }
    if(header_used<12){
        header[header_used++]=byte;frame_last=now;
        if(header_used==12){
            expected=std::size_t(header[6])|(std::size_t(header[7])<<8);
            if(header[4]!=1 || expected>max_payload){reset_frame();deny();}
        }
        return;
    }
    payload[payload_used++]=byte;frame_last=now;
    if(payload_used==expected+4){
        const auto id=u32(header+8);const auto type=header[5];
        if(u32(payload+expected)!=crc(payload,expected,crc(header,12))){reset_frame();fail(type,id,framing);return;}
        handle(type,id,payload,expected);reset_frame();
    }
}
}
extern "C" void app_main() {
    usb_serial_jtag_driver_config_t usb{};usb.tx_buffer_size=2048;usb.rx_buffer_size=8192;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
    std::uint8_t mac[6]{};ESP_ERROR_CHECK(esp_read_mac(mac,ESP_MAC_BASE));
    std::memcpy(context+64,mac,6);
    bootloader_random_enable();esp_fill_random(context+80,16);bootloader_random_disable();
    const bool display_ready=access_ui::start();
    ready=ACCESS_POLICY_CONFIGURED && esp_psram_is_initialized() && display_ready;
    stage=ready?access_ui::Stage::waiting:access_ui::Stage::denied;publish();
    for(;;){
        const auto now=esp_timer_get_time();poll(now);
        if(header_used && (now-frame_last>2000000 || now-frame_started>10000000)){reset_frame();deny();}
        std::uint8_t bytes[256];int n=usb_serial_jtag_read_bytes(bytes,1,pdMS_TO_TICKS(20));
        if(n>0){int extra=usb_serial_jtag_read_bytes(bytes+n,sizeof(bytes)-n,0);if(extra>0)n+=extra;}
        for(int i=0;i<n;++i)feed(bytes[i],esp_timer_get_time());
    }
}

