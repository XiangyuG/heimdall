/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause) */
/* Copyright (c) 2021 Hengqi Chen */
/*
 * Aggressively optimized filetop. Program and map names are unchanged so
 * filetop_runner can load it as-is. Differences from filetop.bpf.c:
 *
 *  - entries is an LRU hash, so a full map never degrades every new key into
 *    lookup + failed update + lookup.
 *  - filename is NAME_MAX + 1 bytes (d_name is one path component) and is
 *    read with bpf_probe_read_kernel_str instead of a 4 KiB raw copy.
 *  - i_mode, i_sb, i_ino and i_rdev are fetched with one probe read of the
 *    inode's first INODE_HDR_SIZE bytes, using CO-RE field offsets; the hot
 *    path does 3 probe reads instead of 9.
 *  - on a miss the whole value (counters included) is built on the stack and
 *    inserted with one BPF_NOEXIST update, so there is no zero_value copy and
 *    no second lookup.
 *  - probe_entry is always inlined so op folds to a constant per program.
 */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>

#define MAX_ENTRIES	10240
#define NAME_MAX	255
#define FILENAME_LEN	(NAME_MAX + 1)
#define TASK_COMM_LEN	16
#define S_IFMT		00170000
#define S_IFSOCK	0140000
#define S_IFREG		0100000

#define S_ISREG(m)	(((m) & S_IFMT) == S_IFREG)
#define S_ISSOCK(m)	(((m) & S_IFMT) == S_IFSOCK)

/* covers i_mode, i_sb, i_ino and i_rdev on x86_64 5.x/6.x layouts */
#define INODE_HDR_SIZE	80

enum op {
	READ,
	WRITE,
};

struct file_id {
	__u64 inode;
	__u32 dev;
	__u32 rdev;
	__u32 pid;
	__u32 tid;
};

struct file_stat {
	__u64 reads;
	__u64 read_bytes;
	__u64 writes;
	__u64 write_bytes;
	__u32 pid;
	__u32 tid;
	char filename[FILENAME_LEN];
	char comm[TASK_COMM_LEN];
	char type;
};

const volatile pid_t target_pid = 0;
const volatile bool regular_file_only = true;

struct {
	__uint(type, BPF_MAP_TYPE_LRU_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct file_id);
	__type(value, struct file_stat);
} entries SEC(".maps");

struct inode_hdr {
	umode_t mode;
	__u32 rdev;
	__u64 ino;
	struct super_block *sb;
};

/* the system libbpf predates bpf_core_field_offset(type, field) */
#define INODE_OFF(f)							\
	__builtin_preserve_field_info(inode->f, BPF_FIELD_BYTE_OFFSET)
#define FIELD_IN_HDR(f)							\
	(INODE_OFF(f) + bpf_core_field_size(inode->f) <= INODE_HDR_SIZE)
#define HDR_FIELD(buf, type, f)						\
	(*(type *)((char *)(buf) + INODE_OFF(f)))

static __always_inline int read_inode_hdr(struct inode *inode,
					  struct inode_hdr *h)
{
	__u64 buf[INODE_HDR_SIZE / sizeof(__u64)];

	/* CO-RE offsets are load-time constants: the verifier keeps exactly
	 * one of these two branches. */
	if (FIELD_IN_HDR(i_mode) && FIELD_IN_HDR(i_sb) &&
	    FIELD_IN_HDR(i_ino) && FIELD_IN_HDR(i_rdev)) {
		if (bpf_probe_read_kernel(buf, sizeof(buf), inode))
			return -1;
		h->mode = HDR_FIELD(buf, umode_t, i_mode);
		h->sb = HDR_FIELD(buf, struct super_block *, i_sb);
		h->ino = HDR_FIELD(buf, unsigned long, i_ino);
		h->rdev = HDR_FIELD(buf, dev_t, i_rdev);
		return 0;
	}

	h->mode = BPF_CORE_READ(inode, i_mode);
	h->sb = BPF_CORE_READ(inode, i_sb);
	h->ino = BPF_CORE_READ(inode, i_ino);
	h->rdev = BPF_CORE_READ(inode, i_rdev);
	return 0;
}

static __always_inline void get_file_path(struct file *file, char *buf,
					  size_t size)
{
	const unsigned char *name;

	name = BPF_CORE_READ(file, f_path.dentry, d_name.name);
	bpf_probe_read_kernel_str(buf, size, name);
}

static __always_inline void account(struct file_stat *v, size_t count,
				    enum op op)
{
	if (op == READ) {
		v->reads++;
		v->read_bytes += count;
	} else {	/* op == WRITE */
		v->writes++;
		v->write_bytes += count;
	}
}

static __always_inline int probe_entry(struct file *file, size_t count,
				       enum op op)
{
	__u64 pid_tgid = bpf_get_current_pid_tgid();
	__u32 pid = pid_tgid >> 32;
	__u32 tid = (__u32)pid_tgid;
	struct file_id key = {};
	struct file_stat *valuep;
	struct inode_hdr h;
	struct super_block *sb;
	struct inode *inode;

	if (target_pid && target_pid != pid)
		return 0;

	inode = BPF_CORE_READ(file, f_inode);
	if (read_inode_hdr(inode, &h))
		return 0;
	if (regular_file_only && !S_ISREG(h.mode))
		return 0;

	/* not BPF_CORE_READ(h.sb, ...): that would emit a relocation for the
	 * local inode_hdr.sb access, which kernel BTF cannot resolve */
	sb = h.sb;
	key.dev = BPF_CORE_READ(sb, s_dev);
	key.rdev = h.rdev;
	key.inode = h.ino;
	key.pid = pid;
	key.tid = tid;

	valuep = bpf_map_lookup_elem(&entries, &key);
	if (valuep) {
		account(valuep, count, op);
		return 0;
	}

	/* miss: build the complete first sample and insert it in one go */
	struct file_stat v = {};

	account(&v, count, op);
	v.pid = pid;
	v.tid = tid;
	bpf_get_current_comm(&v.comm, sizeof(v.comm));
	get_file_path(file, v.filename, sizeof(v.filename));
	if (regular_file_only || S_ISREG(h.mode))
		v.type = 'R';
	else if (S_ISSOCK(h.mode))
		v.type = 'S';
	else
		v.type = 'O';
	if (!bpf_map_update_elem(&entries, &key, &v, BPF_NOEXIST))
		return 0;

	/* lost an insert race with another CPU */
	valuep = bpf_map_lookup_elem(&entries, &key);
	if (valuep)
		account(valuep, count, op);
	return 0;
}

SEC("kprobe/vfs_read")
int BPF_KPROBE(vfs_read_entry, struct file *file, char *buf, size_t count, loff_t *pos)
{
	return probe_entry(file, count, READ);
}

SEC("kprobe/vfs_write")
int BPF_KPROBE(vfs_write_entry, struct file *file, const char *buf, size_t count, loff_t *pos)
{
	return probe_entry(file, count, WRITE);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";
