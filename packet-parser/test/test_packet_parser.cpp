#include "packet_parser.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

using namespace packet_parser;

namespace {

std::vector<uint8_t> create_ipv4_packet()
{
    std::vector<uint8_t> packet = {
        // Ethernet destination
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55,

        // Ethernet source
        0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb,

        // EtherType = IPv4
        0x08, 0x00,

        // IPv4
        // Version = 4
        // IHL = 5
        0x45,

        // DSCP / ECN
        0x00,

        // Total length = 24
        0x00, 0x18,

        // Identification
        0x12, 0x34,

        // Flags / Fragment offset
        0x40, 0x00,

        // TTL
        0x40,

        // Protocol = TCP
        0x06,

        // Header checksum
        0xab, 0xcd,

        // Source = 192.168.1.10
        0xc0, 0xa8, 0x01, 0x0a,

        // Destination = 192.168.1.20
        0xc0, 0xa8, 0x01, 0x14,

        // Payload
        0xde, 0xad, 0xbe, 0xef
    };

    return packet;
}

std::vector<uint8_t> create_ipv6_packet()
{
    std::vector<uint8_t> packet = {
        // Ethernet destination
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55,

        // Ethernet source
        0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb,

        // EtherType = IPv6
        0x86, 0xdd,

        // IPv6
        // Version = 6, Traffic class = 0x2a
        0x62, 0xa1,

        // Flow label = 0x12345
        0x23, 0x45,

        // Payload length = 4
        0x00, 0x04,

        // Next header = TCP
        0x06,

        // Hop limit = 64
        0x40,

        // Source = 2001:db8::1
        0x20, 0x01, 0x0d, 0xb8,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x01,

        // Destination = 2001:db8::2
        0x20, 0x01, 0x0d, 0xb8,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x02,

        // Payload
        0xde, 0xad, 0xbe, 0xef
    };

    return packet;
}

std::vector<uint8_t> make_ipv6_addr(
    const std::vector<uint16_t>& groups)
{
    std::vector<uint8_t> addr;

    for (uint16_t group : groups) {
        addr.push_back(
            static_cast<uint8_t>((group >> 8) & 0xff));
        addr.push_back(
            static_cast<uint8_t>(group & 0xff));
    }

    return addr;
}

void test_valid_ipv4()
{
    PacketParser parser;

    const auto packet = create_ipv4_packet();

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(result.valid);

    assert(result.ipv4.version == 4);
    assert(result.ipv4.ihl == 5);
    assert(result.ipv4.total_length == 24);
    assert(result.ipv4.ttl == 64);
    assert(result.ipv4.protocol == IP_PROTOCOL_TCP);

    assert(result.ipv4.src_addr == 0xc0a8010a);
    assert(result.ipv4.dst_addr == 0xc0a80114);

    assert(result.payload_offset == 34);
    assert(result.payload_length == 4);

    assert(
        ipv4_to_string(result.ipv4.src_addr) ==
        "192.168.1.10"
    );

    assert(
        ipv4_to_string(result.ipv4.dst_addr) ==
        "192.168.1.20"
    );
}

void test_valid_ipv6()
{
    PacketParser parser;

    const auto packet = create_ipv6_packet();

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(result.valid);

    assert(result.ipv6.version == 6);
    assert(result.ipv6.traffic_class == 0x2a);
    assert(result.ipv6.flow_label == 0x12345);
    assert(result.ipv6.payload_length == 4);
    assert(result.ipv6.next_header == IP_PROTOCOL_TCP);
    assert(result.ipv6.hop_limit == 64);

    assert(result.payload_offset == 54);
    assert(result.payload_length == 4);

    assert(
        ipv6_to_string(result.ipv6.src_addr) ==
        "2001:db8::1"
    );

    assert(
        ipv6_to_string(result.ipv6.dst_addr) ==
        "2001:db8::2"
    );
}

void test_ipv6_to_string()
{
    const auto full = make_ipv6_addr(
        {0x2001, 0x0db8, 0x0001, 0x0002,
         0x0003, 0x0004, 0x0005, 0x0006});

    assert(
        ipv6_to_string(full.data()) ==
        "2001:db8:1:2:3:4:5:6"
    );

    const auto compressed = make_ipv6_addr(
        {0x2001, 0x0db8, 0x0000, 0x0000,
         0x0000, 0x0000, 0x0000, 0x0001});

    assert(
        ipv6_to_string(compressed.data()) ==
        "2001:db8::1"
    );

    const auto loopback = make_ipv6_addr(
        {0x0000, 0x0000, 0x0000, 0x0000,
         0x0000, 0x0000, 0x0000, 0x0001});

    assert(
        ipv6_to_string(loopback.data()) ==
        "::1"
    );

    const auto all_zero = make_ipv6_addr(
        {0x0000, 0x0000, 0x0000, 0x0000,
         0x0000, 0x0000, 0x0000, 0x0000});

    assert(
        ipv6_to_string(all_zero.data()) ==
        "::"
    );

    const auto trailing = make_ipv6_addr(
        {0x0001, 0x0002, 0x0003, 0x0004,
         0x0005, 0x0006, 0x0000, 0x0000});

    assert(
        ipv6_to_string(trailing.data()) ==
        "1:2:3:4:5:6::"
    );

    const auto equal_runs = make_ipv6_addr(
        {0x0001, 0x0000, 0x0000, 0x0001,
         0x0000, 0x0000, 0x0001, 0x0001});

    assert(
        ipv6_to_string(equal_runs.data()) ==
        "1::1:0:0:1:1"
    );

    const auto single_zero = make_ipv6_addr(
        {0x0001, 0x0000, 0x0002, 0x0003,
         0x0004, 0x0005, 0x0006, 0x0007});

    assert(
        ipv6_to_string(single_zero.data()) ==
        "1:0:2:3:4:5:6:7"
    );
}

void test_short_ipv6_packet()
{
    PacketParser parser;

    auto packet = create_ipv6_packet();

    packet.resize(14 + 20);

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "packet is shorter than minimum ipv6 header"
    );
}

void test_invalid_ipv6_version()
{
    PacketParser parser;

    auto packet = create_ipv6_packet();

    // Version = 4
    packet[14] = 0x45;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "invalid ipv6 version"
    );
}

void test_ipv6_payload_length_exceeds_packet()
{
    PacketParser parser;

    auto packet = create_ipv6_packet();

    // Payload length = 255, larger than
    // the remaining bytes.
    packet[18] = 0x00;
    packet[19] = 0xff;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "ipv6 payload length exceeds packet length"
    );
}

void test_ipv6_exact_header()
{
    PacketParser parser;

    auto packet = create_ipv6_packet();

    // Exact IPv6 base header, no payload.
    packet.resize(14 + 40);

    // Payload length = 0
    packet[18] = 0x00;
    packet[19] = 0x00;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(result.valid);
    assert(result.payload_offset == 54);
    assert(result.payload_length == 0);
}

void test_null_input()
{
    PacketParser parser;

    ParsedPacket result =
        parser.parse(nullptr, 10);

    assert(!result.valid);
    assert(result.error == "input data is null");
}

void test_empty_packet()
{
    PacketParser parser;

    const std::vector<uint8_t> packet;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(result.error == "input packet is empty");
}

void test_short_ethernet_packet()
{
    PacketParser parser;

    const std::vector<uint8_t> packet = {
        0x00, 0x11, 0x22
    };

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "packet is shorter than ethernet header"
    );
}

void test_non_ipv4_packet()
{
    PacketParser parser;

    auto packet = create_ipv4_packet();

    // Change EtherType to ARP.
    packet[12] = 0x08;
    packet[13] = 0x06;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "unsupported ethernet protocol"
    );
}

void test_invalid_ipv4_version()
{
    PacketParser parser;

    auto packet = create_ipv4_packet();

    // Version = 5
    packet[14] = 0x55;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "invalid ipv4 version"
    );
}

void test_invalid_ipv4_ihl()
{
    PacketParser parser;

    auto packet = create_ipv4_packet();

    // Version = 4, IHL = 4
    packet[14] = 0x44;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "invalid ipv4 ihl"
    );
}

void test_invalid_total_length()
{
    PacketParser parser;

    auto packet = create_ipv4_packet();

    // Total length = 10,
    // smaller than IPv4 header.
    packet[16] = 0x00;
    packet[17] = 0x0a;

    ParsedPacket result =
        parser.parse(packet.data(), packet.size());

    assert(!result.valid);
    assert(
        result.error ==
        "invalid ipv4 total length"
    );
}

} // namespace

int main()
{
    test_valid_ipv4();
    test_null_input();
    test_empty_packet();
    test_short_ethernet_packet();
    test_non_ipv4_packet();
    test_invalid_ipv4_version();
    test_invalid_ipv4_ihl();
    test_invalid_total_length();
    test_valid_ipv6();
    test_ipv6_to_string();
    test_short_ipv6_packet();
    test_invalid_ipv6_version();
    test_ipv6_payload_length_exceeds_packet();
    test_ipv6_exact_header();

    std::cout << "All tests passed." << std::endl;

    return 0;
}