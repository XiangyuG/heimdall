/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause) */
/* Copyright (c) 2021 Hengqi Chen */

#include "vmlinux.h"

#include <bpf/bpf_helpers.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_tracing.h>

#define MAX_ENTRIES	10240
#define PATH_MAX	4096
#define TASK_COMM_LEN	16

#define S_IFMT		00170000
#define S_IFSOCK	0140000
#define S_IFLNK		0120000
#define S_IFREG		0100000
#define S_IFBLK		0060000
#define S_IFDIR		0040000
#define S_IFCHR		0020000
#define S_IFIFO		0010000

#define S_ISREG(m)	(((m) & S_IFMT) == S_IFREG)
#define S_ISSOCK(m)	(((m) & S_IFMT) == S_IFSOCK)

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
	char filename[PATH_MAX];
	char comm[TASK_COMM_LEN];
	char type;
};

const volatile pid_t target_pid = 0;
const volatile bool regular_file_only = true;

static struct file_stat zero_value = {};

struct {
	__uint(type, BPF_MAP_TYPE_LRU_PERCPU_HASH);
	__uint(max_entries, MAX_ENTRIES);
	__type(key, struct file_id);
	__type(value, struct file_stat);
} entries SEC(".maps");

static __always_inline struct file_stat *
lookup_or_init(const struct file_id *key)
{
	struct file_stat *value;

	value = bpf_map_lookup_elem(&entries, key);
	if (value)
		return value;

	bpf_map_update_elem(&entries, key, &zero_value, BPF_NOEXIST);
	return bpf_map_lookup_elem(&entries, key);
}

static __always_inline void get_file_path(struct file *file, char *buf, size_t size)
{
	const unsigned char *name;

	name = BPF_CORE_READ(file, f_path.dentry, d_name.name);
	bpf_probe_read_kernel_str(buf, size, name);
}

static __always_inline int probe_entry(struct file *file, size_t count, enum op op)
{
	__u64 pid_tgid = bpf_get_current_pid_tgid();
	__u32 pid = pid_tgid >> 32;
	__u32 tid = (__u32)pid_tgid;

	struct inode *inode;
	struct super_block *sb;
	struct file_id key = {};
	struct file_stat *valuep;
	umode_t mode;

	if (target_pid && target_pid != pid)
		return 0;

	inode = BPF_CORE_READ(file, f_inode);
	if (!inode)
		return 0;

	mode = BPF_CORE_READ(inode, i_mode);

	if (regular_file_only && !S_ISREG(mode))
		return 0;

	sb = BPF_CORE_READ(inode, i_sb);

	key.inode = BPF_CORE_READ(inode, i_ino);
	key.rdev = BPF_CORE_READ(inode, i_rdev);
	key.dev = sb ? BPF_CORE_READ(sb, s_dev) : 0;
	key.pid = pid;
	key.tid = tid;

	valuep = lookup_or_init(&key);
	if (!valuep)
		return 0;

	if (valuep->pid == 0 && valuep->tid == 0) {
		valuep->pid = pid;
		valuep->tid = tid;

		bpf_get_current_comm(&valuep->comm, sizeof(valuep->comm));
		get_file_path(file, valuep->filename, sizeof(valuep->filename));

		if (S_ISREG(mode))
			valuep->type = 'R';
		else if (S_ISSOCK(mode))
			valuep->type = 'S';
		else
			valuep->type = 'O';
	}

	if (op == READ) {
		valuep->reads++;
		valuep->read_bytes += count;
	} else {
		valuep->writes++;
		valuep->write_bytes += count;
	}

	return 0;
}

SEC("kprobe/vfs_read")
int BPF_KPROBE(vfs_read_entry, struct file *file, char *buf,
	       size_t count, loff_t *pos)
{
	return probe_entry(file, count, READ);
}

SEC("kprobe/vfs_write")
int BPF_KPROBE(vfs_write_entry, struct file *file, const char *buf,
	       size_t count, loff_t *pos)
{
	return probe_entry(file, count, WRITE);
}

char LICENSE[] SEC("license") = "Dual BSD/GPL";
