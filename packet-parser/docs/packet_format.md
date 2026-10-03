# Packet Format

## 1. Overview

The packet parser supports Ethernet frames carrying IPv4 packets.

Current protocol stack:

Ethernet
    |
    +-- IPv4
          |
          +-- TCP
          +-- UDP
          +-- ICMP

## 2. Ethernet Header

Ethernet header size:

```text
14 bytes