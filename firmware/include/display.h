#pragma once
#include <cstddef>
#include <cstdint>
namespace access_ui {
enum class Stage { ready, waiting, challenge, receiving, verifying, granted, denied, expired };
struct Snapshot {
    Stage stage = Stage::ready;
    std::uint32_t proof_bytes=0, verify_us=0, heap=0, min_heap=0;
    std::uint32_t successes=0, rejected=0, operation=0, config=0;
    bool maintenance=false, valid=false, checked=false;
};
bool start();
void update(const Snapshot &snapshot);
std::uint32_t selected_operation();
bool healthy();
std::uint32_t frames_rendered();
bool touch_healthy();
std::uint32_t render_us();
}

