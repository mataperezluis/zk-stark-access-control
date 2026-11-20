#![no_std]
extern crate alloc;
use core::alloc::{GlobalAlloc, Layout};
extern "C" {
    fn access_alloc(size: usize, alignment: usize) -> *mut core::ffi::c_void;
    fn access_free(ptr: *mut core::ffi::c_void);
    fn abort() -> !;
}
struct EspAllocator;
unsafe impl GlobalAlloc for EspAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        access_alloc(layout.size().max(1), layout.align()) as *mut u8
    }
    unsafe fn dealloc(&self, ptr: *mut u8, _: Layout) { access_free(ptr.cast()); }
}
#[global_allocator]
static ALLOCATOR: EspAllocator = EspAllocator;
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! { unsafe { abort() } }

/// Only this function may return the successful cryptographic verification verdict.
/// All buffers must be readable for the declared sizes. No ownership crosses the ABI.
#[no_mangle]
pub unsafe extern "C" fn access_zk_verify(proof: *const u8, proof_len: usize,
    public: *const u8, public_len: usize, context: *const u8, context_len: usize) -> i32 {
    if proof.is_null() || public.is_null() || context.is_null() || proof_len == 0 ||
       proof_len > access_zk::MAX_PROOF_SIZE || public_len != access_zk::PUBLIC_BYTES ||
       context_len != access_zk::CONTEXT_BYTES { return 1; }
    let proof = core::slice::from_raw_parts(proof, proof_len);
    let public = core::slice::from_raw_parts(public, public_len);
    let context = core::slice::from_raw_parts(context, context_len);
    if access_zk::verify(proof, public, context).is_ok() { 0 } else { 1 }
}

