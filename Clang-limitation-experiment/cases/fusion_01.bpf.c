// SPDX-License-Identifier: GPL-2.0
// Standalone loop-fusion case: repeated updates are observed through b[0].
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

// restrict excludes overlapping arrays; only same-index dependencies exist.
// Keep this boundary to test optimization within the helper independently.
__attribute__((noinline))
static void kernel(u32 *restrict a, u32 *restrict b, u32 n)
{
    for (u32 i = 0; i < n; i++) {
        a[i] += 1;
    }
    for (u32 i = 0; i < n; i++) {
        b[i] = a[i] * 3;
    }
}

__attribute__((section("kprobe/test")))
u32 entry(const u32 *ctx)
{
    u32 a[8] = {0};
    u32 b[8] = {0};
    const u32 n = *ctx;

    for (u32 r = 0; r < 1; r++)
        kernel(a, b, n);

    return b[0];
}
