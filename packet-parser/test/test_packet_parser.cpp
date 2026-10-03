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

    // Change EtherType to IPv6.
    packet[12] = 0x86;
    packet[13] = 0xdd;

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

    std::cout << "All tests passed." << std::endl;

    return 0;
}