#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
int access_zk_verify(const uint8_t *proof, size_t proof_len,
    const uint8_t *public_inputs, size_t public_len, const uint8_t *context, size_t context_len);
#ifdef __cplusplus
}
#endif

