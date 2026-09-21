"""Benchmark-scoped online state merging for map-free eBPF programs."""

from __future__ import annotations

import struct
from pathlib import Path

import angr
from angr.errors import SimMergeError
from angr.exploration_techniques import ManualMergepoint
from elftools.elf.elffile import ELFFile

from angr_ebpf.simos_ebpf import EbpfMapManager


_BPF_JMP = 0x05
_BPF_JMP32 = 0x06
_BPF_CLASS_MASK = 0x07
_BPF_OP_MASK = 0xF0
_BPF_JA = 0x00
_BPF_CALL = 0x80
_BPF_EXIT = 0x90
_INSN_SIZE = 8


def find_forward_conditional_join_offsets(object_path: Path, entry_symbol: str):
    """Return convergence offsets for simple forward conditional branches."""

    with object_path.open("rb") as object_file:
        elf = ELFFile(object_file)
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None:
            raise ValueError(f"{object_path} has no symbol table")

        symbol = next(
            (candidate for candidate in symtab.iter_symbols() if candidate.name == entry_symbol),
            None,
        )
        if symbol is None:
            raise ValueError(f"entry symbol {entry_symbol!r} not found in {object_path}")

        section_index = symbol["st_shndx"]
        if not isinstance(section_index, int):
            raise ValueError(f"entry symbol {entry_symbol!r} has no concrete section")

        section = elf.get_section(section_index)
        symbol_start = int(symbol["st_value"])
        symbol_size = int(symbol["st_size"])
        code = section.data()[symbol_start : symbol_start + symbol_size]

    if len(code) % _INSN_SIZE != 0:
        raise ValueError("eBPF function size is not instruction-aligned")

    join_offsets = []
    instruction_count = len(code) // _INSN_SIZE
    for index in range(instruction_count):
        instruction = code[index * _INSN_SIZE : (index + 1) * _INSN_SIZE]
        opcode = instruction[0]
        instruction_class = opcode & _BPF_CLASS_MASK
        operation = opcode & _BPF_OP_MASK
        if instruction_class not in (_BPF_JMP, _BPF_JMP32):
            continue
        if operation in (_BPF_JA, _BPF_CALL, _BPF_EXIT):
            continue

        jump_delta = struct.unpack_from("<h", instruction, 2)[0]
        target_index = index + 1 + jump_delta
        if jump_delta < 0 or target_index <= index or target_index >= instruction_count:
            raise ValueError(
                "online merging only supports forward, acyclic branch diamonds"
            )

        fallthrough = code[(index + 1) * _INSN_SIZE : target_index * _INSN_SIZE]
        for body_index in range(len(fallthrough) // _INSN_SIZE):
            body_opcode = fallthrough[body_index * _INSN_SIZE]
            if (body_opcode & _BPF_CLASS_MASK) in (_BPF_JMP, _BPF_JMP32):
                raise ValueError(
                    "conditional target is not a simple if-without-else convergence point"
                )
        join_offsets.append(target_index * _INSN_SIZE)

    return tuple(sorted(set(join_offsets)))


def install_online_merging(join_offsets):
    """Temporarily install online merging and return statistics plus restore hook."""

    join_offsets = tuple(join_offsets)
    if not join_offsets:
        raise ValueError("no convergence points were discovered")

    statistics = {
        "join_points": len(join_offsets),
        "merge_calls": 0,
        "states_before_merge": 0,
        "states_after_merge": 0,
    }

    original_explore = angr.SimulationManager.explore
    original_merge = angr.SimulationManager.merge
    original_map_merge = EbpfMapManager.merge

    def merge_empty_map_plugin(self, others, merge_conditions, common_ancestor=None):
        del merge_conditions, common_ancestor
        managers = [self, *others]
        if any(manager._maps_by_index for manager in managers):
            raise SimMergeError("online merging is limited to map-free programs")
        storage_ptrs = {manager._value_storage_ptr for manager in managers}
        write_counters = {manager._write_counter for manager in managers}
        if len(storage_ptrs) != 1 or len(write_counters) != 1:
            raise SimMergeError("empty eBPF map-manager metadata differs between states")
        return False

    def measured_merge(self, *args, **kwargs):
        stash = kwargs.get("stash", "active")
        before = len(self.stashes.get(stash, ()))
        if before > 1:
            statistics["merge_calls"] += 1
            statistics["states_before_merge"] += before
        result = original_merge(self, *args, **kwargs)
        after = len(self.stashes.get(stash, ()))
        if before > 1:
            statistics["states_after_merge"] += after
        return result

    def explore_with_mergepoints(self, *args, **kwargs):
        if not self.active:
            return original_explore(self, *args, **kwargs)
        entry_address = self.active[0].addr
        for offset in join_offsets:
            self.use_technique(
                ManualMergepoint(entry_address + offset, wait_counter=64, prune=True)
            )
        return original_explore(self, *args, **kwargs)

    EbpfMapManager.merge = merge_empty_map_plugin
    angr.SimulationManager.merge = measured_merge
    angr.SimulationManager.explore = explore_with_mergepoints

    def restore():
        angr.SimulationManager.explore = original_explore
        angr.SimulationManager.merge = original_merge
        EbpfMapManager.merge = original_map_merge

    return statistics, restore
