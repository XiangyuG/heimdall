// SPDX-License-Identifier: GPL-2.0
// Standalone bound-caching case: the final result is observed through a[0].
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

// Every call supplies distinct local arrays and a separate local int bound.
// No stores in this helper can modify that bound on these calls.
__attribute__((noinline))
static void kernel(u32 *a, const u32 *b, const int *n)
{
    const int _heimdall_bound = *n;
    for (int i = 0; i < _heimdall_bound; i++) {
        a[i] = b[i] + 1;
    }
}

__attribute__((section("kprobe/test")))
u32 entry(const u32 *ctx)
{
    u32 a[8] = {0};
    u32 b[8] = {0};
    int n = (int)*ctx;

    for (u32 r = 0; r < 32; r++)
        kernel(a, b, &n);

    return a[0];
}
