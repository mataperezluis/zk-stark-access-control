#include "esp_heap_caps.h"
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
namespace {
struct Header { void *base; std::size_t bytes; };
std::size_t current=0, peak=0;
constexpr std::size_t budget=6*1024*1024;
}
extern "C" void *access_alloc(std::size_t size,std::size_t alignment) {
    if(size>budget || current>budget-size) return nullptr;
    alignment=std::max(alignment,alignof(Header));
    if(alignment>4096 || size>budget-sizeof(Header)-alignment) return nullptr;
    void *base=heap_caps_malloc(size+sizeof(Header)+alignment,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!base) return nullptr;
    auto address=(reinterpret_cast<std::uintptr_t>(base)+sizeof(Header)+alignment-1)&~(alignment-1);
    auto *header=reinterpret_cast<Header *>(address)-1;
    header->base=base; header->bytes=size;
    current+=size; peak=std::max(peak,current);
    return reinterpret_cast<void *>(address);
}
extern "C" void access_free(void *ptr) {
    if(!ptr) return;
    auto *header=static_cast<Header *>(ptr)-1;
    current-=header->bytes; heap_caps_free(header->base);
}
extern "C" std::size_t access_peak() { return peak; }
extern "C" void access_reset_peak() { peak=current; }

