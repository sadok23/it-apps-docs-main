# e1000e Detected Hardware Unit Hang — Fix & Revert

## Affected Hardware

- **NIC**: Intel I219/I218 (e1000e driver)
- **Symptom**: Server loses network connectivity, kernel logs repeat every 2 seconds:
  ```
  e1000e 0000:00:1f.6 nic0: Detected Hardware Unit Hang
  ```
- **Only recovery without fix**: Unplug and replug the network cable

---

## Root Cause

The Intel I219/I218 NIC has a hardware bug in its TCP Segmentation Offload (TSO) circuit. When TSO is enabled, the kernel hands large data blobs to the NIC to cut into packets. Under certain traffic conditions, the NIC freezes mid-operation and never signals completion to the kernel. The TX queue stalls entirely. The driver cannot recover in software — only a full PHY reset (cable replug) clears it.

---

## Fix

Disable TSO, GSO, and GRO — moving segmentation from the broken NIC hardware back to the CPU. At 1Gbps this has negligible performance impact.

### Step 1 — Apply live (no reboot, no link drop)

```bash
ethtool -K nic0 tso off gso off gro off
```

Verify:

```bash
ethtool -k nic0 | grep -E "tcp-segmentation|generic-segmentation|generic-receive"
```

All three should show `off`.

### Step 2 — Make persistent across reboots

Edit `/etc/network/interfaces` and add the `post-up` line to the `nic0` block:

```
iface nic0 inet manual
        post-up ethtool -K nic0 tso off gso off gro off
```

Full file example:

```
auto lo
iface lo inet loopback

iface nic0 inet manual
        post-up ethtool -K nic0 tso off gso off gro off

auto vmbr0
iface vmbr0 inet static
        address 20.0.0.202/22
        gateway 20.0.0.1
        bridge-ports nic0
        bridge-stp off
        bridge-fd 0

iface nic1 inet manual

source /etc/network/interfaces.d/*
```

No restart required after editing the file — the `post-up` hook runs automatically on next boot.

---

## Revert

### Live (immediate)

```bash
ethtool -K nic0 tso on gso on gro on
```

### Persistent

Remove the `post-up` line from `/etc/network/interfaces`:

```
iface nic0 inet manual
```

---


