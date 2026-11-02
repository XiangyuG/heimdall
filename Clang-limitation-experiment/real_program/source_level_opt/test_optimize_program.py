"""Discovery and rejection tests independent of corpus filenames and recipe offsets."""
import tempfile
import unittest
from pathlib import Path
from optimize_program import Program, local_alignment, aligned_maps, cache_bounds, find_clang


class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clang = find_clang()

    def program(self, text):
        return Program('/private/tmp/unseen-program.c', text.encode(), ['-target','bpfel','-O2'], self.clang)

    def test_aggregate_with_new_names(self):
        s = self.program('struct novel { int x; char y[13]; }; int arbitrary(void) { struct novel z = {}; return z.x; }')
        changes = local_alignment(s)
        self.assertEqual(len(changes), 1)
        self.assertIn(b'aligned(8)', s.apply(changes[0].edits))

    def test_multideclarator_and_pointer_rejected(self):
        s = self.program('struct s { int a; }; int f(void) { struct s a={}, b={}; struct s *p=&a; return b.a; }')
        self.assertEqual(local_alignment(s), [])

    def test_alignof_observation_rejected(self):
        s = self.program('struct s { int a; }; int f(void) { struct s a={}; return __alignof__(a); }')
        self.assertEqual(local_alignment(s), [])

    def test_volatile_requires_contract_and_keeps_pragma(self):
        text = 'const volatile int unseen_limit=9; int f(void) { int x=0;\n#pragma unroll\nfor(int k=0;k<unseen_limit;k++) x+=k; return x; }'
        s = self.program(text)
        self.assertEqual(cache_bounds(s, False), [])
        changes = cache_bounds(s, True)
        self.assertEqual(len(changes), 1)
        transformed = s.apply(changes[0].edits)
        self.assertIn(b'#pragma unroll\nfor', transformed)
        self.assertLess(transformed.index(b'_heimdall_cached_'), transformed.index(b'#pragma'))
        self.program(transformed.decode())

    def test_zero_guard_uses_same_cached_value(self):
        s = self.program('const volatile int cap=9; int f(void) { if(cap==0) return 0; for(int k=0;k<cap;k++) {} return 1; }')
        changes = cache_bounds(s, True)
        self.assertEqual(len(changes), 1)
        text = s.apply(changes[0].edits).decode()
        self.assertIn('if(_heimdall_cached_cap==0)', text)
        self.assertIn('k<_heimdall_cached_cap', text)

    def test_stack_address_observation_rejected(self):
        for text in (
            'struct s { int a; }; unsigned long leak(void *p) { return (unsigned long)p; } unsigned long f(void) { struct s a={}; return leak(&a); }',
            'struct s { int a; }; unsigned long f(void) { struct s a={}; return (unsigned long)&a; }',
            'struct s { int a; }; unsigned long f(void *p) { struct s a={}; p=&a; return (unsigned long)p; }',
        ):
            self.assertEqual(local_alignment(self.program(text)), [])

    def test_mutable_global_bound_rejected(self):
        s = self.program('int cap=9; int f(void) { int x=0; for(int k=0;k<cap;k++) x+=k; return x; }')
        self.assertEqual(cache_bounds(s, True), [])

    def test_shadowed_lookup_rejected(self):
        s = self.program('void *bpf_map_lookup_elem(void *m, void *k) { return m; } int f(void) { int m,k; return bpf_map_lookup_elem(&m,&k)!=0; }')
        self.assertEqual(aligned_maps(s), [])

    def test_stack_address_contract_is_explicit(self):
        s = self.program('struct s { int a; }; unsigned long f(void *p) { struct s a={}; return (unsigned long)p + a.a; }')
        self.assertEqual(local_alignment(s), [])
        self.assertEqual(len(local_alignment(s, stack_addresses_unobserved=True)), 1)
        s = self.program('struct s { int a; }; int f(void) { struct s a={}; return __alignof__(a); }')
        self.assertEqual(local_alignment(s, stack_addresses_unobserved=True), [])

    def test_unknown_address_observer_rejected(self):
        s = self.program('struct s { int a; }; extern void observe(void *); int f(void) { struct s a={}; observe(&a); return a.a; }')
        self.assertEqual(local_alignment(s), [])

    def test_arithmetic_helper_initializer_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = '#include "h.h"\nstruct { int (*type)[1]; int *value; } m __attribute__((section(".maps"))); int f(void) { int k=0; return bpf_map_lookup_elem(&m,&k)!=0; }'
            # Even constant arithmetic must fail the structural helper check.
            Path(tmp,'h.h').write_text('static void *(*const bpf_map_lookup_elem)(void *,const void *)=(void *)(1 << 0);')
            s = Program(Path(tmp,'new.c'), text.encode(), ['-target','bpfel','-O2'], self.clang)
            self.assertEqual(aligned_maps(s), [])

    def test_mutable_pointer_to_const_return_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'h.h').write_text('static const void *(*bpf_map_lookup_elem)(void *,const void *)=(void *)1;')
            text = '#include "h.h"\nstruct { int (*type)[1]; int *value; } m __attribute__((section(".maps"))); int f(void) { int k=0; return bpf_map_lookup_elem(&m,&k)!=0; }'
            s = Program(Path(tmp,'new.c'), text.encode(), ['-target','bpfel','-O2'], self.clang)
            self.assertEqual(aligned_maps(s), [])

    def test_known_map_types_only(self):
        # A real helper declaration in an included header, identified by AST and ID1.
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'h.h').write_text('static void *(*const bpf_map_lookup_elem)(void *,const void *)=(void *)1;')
            for map_type in (1, 2, 5, 6, 9, 10, 11, 27):
                text = f'#include "h.h"\nstruct {{ int (*type)[{map_type}]; int *key; int *value; }} unfamiliar __attribute__((section(".maps"))); int f(void) {{ int key=0; return bpf_map_lookup_elem(&unfamiliar,&key)!=0; }}'
                s = Program(Path(tmp,'new.c'), text.encode(), ['-target','bpfel','-O2'], self.clang)
                self.assertEqual(bool(aligned_maps(s)), map_type in {1,2,5,6,9,10})


if __name__ == '__main__':
    unittest.main()
