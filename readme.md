## Download the kernel and extract it

```bash
curl -O https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.17.9.tar.xz
tar -xf linux-6.17.9.tar.xz
rm linux-6.17.9.tar.xz
cd linux-6.17.9
```

## Save the current working directory as an environment variable (for easy navigation)

```bash
export KERNEL_DIR=$(pwd)
```

## Modify `kernel/sys.c`

```bash
cd kernel
gedit sys.c
```

Add the following at the end of the file:

```c
// --- System Call Implementation Starts ---

/**
 * sum_rusage - Helper function to add the resource usage of 'add' into 'total'.
 * @total: The cumulative rusage struct.
 * @add: The rusage struct to add.
 *
 * Correctly normalizes timevals and finds the maximum RSS.
 */
static void sum_rusage(struct rusage *total, const struct rusage *add)
{
    // Sum user and system time components
    total->ru_utime.tv_sec += add->ru_utime.tv_sec;
    total->ru_utime.tv_usec += add->ru_utime.tv_usec;
    total->ru_stime.tv_sec += add->ru_stime.tv_sec;
    total->ru_stime.tv_usec += add->ru_stime.tv_usec;

    // Normalize user time (Microseconds to Seconds)
    while (total->ru_utime.tv_usec >= USEC_PER_SEC) {
        total->ru_utime.tv_sec++;
        total->ru_utime.tv_usec -= USEC_PER_SEC;
    }
    // Normalize system time (Microseconds to Seconds)
    while (total->ru_stime.tv_usec >= USEC_PER_SEC) {
        total->ru_stime.tv_sec++;
        total->ru_stime.tv_usec -= USEC_PER_SEC;
    }

    // ru_maxrss is the "high-water mark,"
    total->ru_maxrss = max(total->ru_maxrss, add->ru_maxrss);

    // Other fields are simple sums
    total->ru_minflt += add->ru_minflt;
    total->ru_majflt += add->ru_majflt;
    total->ru_inblock += add->ru_inblock;
    total->ru_oublock += add->ru_oublock;
    total->ru_nvcsw += add->ru_nvcsw;
    total->ru_nivcsw += add->ru_nivcsw;
}

/**
 * signal_struct_to_rusage - Converts signal_struct time values (nanoseconds)
 * to a rusage struct (seconds/microseconds).
 *
 * NOTE: Using (long) casts for tv_sec/tv_usec to avoid ambiguity with
 * kernel time types.
 */
static void signal_struct_to_rusage(struct rusage *r, s64 utime, s64 stime, long maxrss,
                                    long minflt, long majflt, long inblock,
                                    long oublock, long nvcsw, long nivcsw)
{
    memset(r, 0, sizeof(*r));

    // Convert nanoseconds (s64) to seconds and microseconds using long cast
    r->ru_utime.tv_sec = (long)(utime / NSEC_PER_SEC);
    r->ru_utime.tv_usec = (long)((utime % NSEC_PER_SEC) / NSEC_PER_USEC);

    r->ru_stime.tv_sec = (long)(stime / NSEC_PER_SEC);
    r->ru_stime.tv_usec = (long)((stime % NSEC_PER_SEC) / NSEC_PER_USEC);

    // Copy other fields
    r->ru_maxrss = maxrss;
    r->ru_minflt = minflt;
    r->ru_majflt = majflt;
    r->ru_inblock = inblock;
    r->ru_oublock = oublock;
    r->ru_nvcsw = nvcsw;
    r->ru_nivcsw = nivcsw;
}


/**
 * __traverse_and_sum - Recursively traverse the process tree and sum usage.
 * @task: The current task_struct to process.
 * @total: The cumulative rusage struct.
 * @log_enabled: If true, printk logs process contributions.
 *
 * This function must be called with RCU read lock held.
 */
static void __traverse_and_sum(struct task_struct *task, struct rusage *total, bool log_enabled)
{
    struct task_struct *child;
    struct signal_struct *sig;
    struct rusage r;

    sig = task->signal;
    if (sig) {

        // 1. Add usage from the current thread group (process)
        signal_struct_to_rusage(&r, sig->utime, sig->stime, sig->maxrss,
                                sig->min_flt, sig->maj_flt, sig->inblock,
                                sig->oublock, sig->nvcsw, sig->nivcsw);
        sum_rusage(total, &r);

        if (log_enabled) {
            printk(KERN_INFO "RUSAGE_LOG: PID %d (%s) - Added Current Usage. UT: %ld.%06ld, ST: %ld.%06ld, MaxRSS: %ld\n",
                   task_tgid_vnr(task), task->comm,
                   (long)r.ru_utime.tv_sec, (long)r.ru_utime.tv_usec,
                   (long)r.ru_stime.tv_sec, (long)r.ru_stime.tv_usec,
                   r.ru_maxrss);
        }

        // 2. Add cumulative usage from reaped (dead) children
        signal_struct_to_rusage(&r, sig->cutime, sig->cstime, sig->cmaxrss,
                                sig->cmin_flt, sig->cmaj_flt, sig->cinblock,
                                sig->coublock, sig->cnvcsw, sig->cnivcsw);
        sum_rusage(total, &r);

        if (log_enabled && (sig->cutime > 0 || sig->cstime > 0)) {
            printk(KERN_INFO "RUSAGE_LOG: PID %d (%s) - Added Reaped Children Cumulative Usage. CUT: %ld.%06ld, CST: %ld.%06ld, CMaxRSS: %ld\n",
                   task_tgid_vnr(task), task->comm,
                   (long)r.ru_utime.tv_sec, (long)r.ru_utime.tv_usec,
                   (long)r.ru_stime.tv_sec, (long)r.ru_stime.tv_usec,
                   r.ru_maxrss);
        }
    }

    // 3. Recurse for all living children
    list_for_each_entry_rcu(child, &task->children, sibling) {
        __traverse_and_sum(child, total, log_enabled);
    }
}


// --- System Call 1: Standard Subtree Rusage ---

/**
 * sys_get_proc_subtree_rusage - Custom syscall to aggregate resource usage
 * for a process and all its descendants without logging.
 * @pid: The PID of the root process of the subtree.
 * @flags: Reserved for future use (currently unused).
 * @usage: The user-space pointer to a 'struct rusage' to fill.
 *
 * Returns 0 on success, or a negative errno on failure.
 */
SYSCALL_DEFINE3(get_proc_subtree_rusage, pid_t, pid, int, flags, struct rusage __user *, usage)
{
    struct rusage total_usage;
    struct task_struct *p;
    long ret = 0;

    memset(&total_usage, 0, sizeof(total_usage));

    rcu_read_lock();

    p = find_task_by_vpid(pid);
    if (!p) {
        ret = -ESRCH; // No such process
        goto out_unlock;
    }

    // Call traversal without logging (log_enabled = false)
    __traverse_and_sum(p, &total_usage, false);

out_unlock:
    rcu_read_unlock();

    if (ret)
        return ret;

    // Copy result to user space
    if (copy_to_user(usage, &total_usage, sizeof(total_usage))) {
        return -EFAULT; // Bad user-space address
    }

    return 0; // Success
}


```

## Modify `arch/x86/entry/syscalls/syscall_64.tbl`

```bash
cd $KERNEL_DIR
cd arch/x86/entry/syscalls
gedit syscall_64.tbl
```

Add the following at the end of the file:

```
470     common  get_proc_subtree_rusage sys_get_proc_subtree_rusage
```

**make sure the numbers are not used**

## Modify `include/linux/syscalls.h`

```bash
cd $KERNEL_DIR
cd include/linux
gedit syscalls.h
```

Add the following at the end of the file:

```c
asmlinkage long sys_get_proc_subtree_rusage(pid_t pid, int flags, struct rusage __user *usage);
```

## GRUB Menu Appearance Configuration

File: `/etc/default/grub`

```bash
sudo nano /etc/default/grub
```

```bash
GRUB_DEFAULT=1
GRUB_TIMEOUT_STYLE=menu
GRUB_TIMEOUT=5
```

Update GRUB after editing:

```bash
sudo update-grub
```

Reboot and boot up using the new kernel

```bash
sudo reboot
```

## Install Essentials for Kernel Build

```bash
sudo apt update && sudo apt install -y build-essential bison flex libncurses-dev libelf-dev libssl-dev libdw-dev dwarves tar xz-utils util-linux
```

## Compile the kernel

#### Return to root directory

```bash
cd $KERNEL_DIR
```

#### Get the old configuration

```bash
cp -v /boot/config-$(uname -r) .config
```

```bash
make menuconfig
```

#### Optional Step: You can add your name as the kernel name

```
General setup  --->
    () Local version - append to kernel release
```

Put something like `-sayan`

Save and exit.

#### Edit the `.config` file

```bash
gedit .config
```

Look for `CONFIG_SYSTEM_TRUSTED_KEYS` and `CONFIG_SYSTEM_REVOCATION_KEYS` and edit them as follows

```
CONFIG_SYSTEM_TRUSTED_KEYS=""
CONFIG_SYSTEM_REVOCATION_KEYS=""
```

#### Build the kernel

```bash
make -j$(nproc) 2>&1 | tee build.log
```

#### Install kernel modules

```bash
sudo make modules_install
```

#### Install the Kernel

```bash
sudo make install
```
