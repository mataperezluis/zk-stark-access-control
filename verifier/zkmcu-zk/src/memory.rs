use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
pub struct Counting;
static CURRENT: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);
unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let p = unsafe { System.alloc(layout) };
        if !p.is_null() {
            let n = CURRENT.fetch_add(layout.size(), Relaxed) + layout.size();
            PEAK.fetch_max(n, Relaxed);
        }
        p
    }
    unsafe fn dealloc(&self, p: *mut u8, layout: Layout) {
        CURRENT.fetch_sub(layout.size(), Relaxed);
        unsafe { System.dealloc(p, layout); }
    }
}
#[global_allocator]
static ALLOCATOR: Counting = Counting;
pub fn reset() -> usize {
    let n = CURRENT.load(Relaxed); PEAK.store(n, Relaxed); n
}
pub fn peak_additional(baseline: usize) -> usize { PEAK.load(Relaxed).saturating_sub(baseline) }

