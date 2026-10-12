// SPDX-License-Identifier: GPL-2.0
// Read distinct aligned u16 objects and add their values to the result.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

static __attribute__((always_inline)) inline u32 kernel(const u8 *p)
{
    /* heimdall:aligned-u16-object p */
    return (u32)p[0] | ((u32)p[1] << 8);
}

__attribute__((section("kprobe/test")))
u32 entry(const u16 *ctx)
{
    u32 s = 0;

    for (u32 i = 0; i < 32; i++)
        s += kernel((const u8 *)&ctx[i]);

    return s;
}
