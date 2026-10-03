#ifndef PACKET_PARSER_H
#define PACKET_PARSER_H

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace packet_parser {

// ============================================================
// Protocol constants
// ============================================================

constexpr uint16_t ETHERTYPE_IPV4 = 0x0800;
constexpr uint16_t ETHERTYPE_IPV6 = 0x86DD;

constexpr uint8_t IP_PROTOCOL_ICMP = 1;
constexpr uint8_t IP_PROTOCOL_TCP  = 6;
constexpr uint8_t IP_PROTOCOL_UDP  = 17;

// ============================================================
// Ethernet header
// ============================================================

struct EthernetHeader {
    uint8_t dst_mac[6]{};
    uint8_t src_mac[6]{};
    uint16_t ether_type = 0;
};

// ============================================================
// IPv4 header
// ============================================================

struct IPv4Header {
    uint8_t version = 0;
    uint8_t ihl = 0;

    uint8_t dscp = 0;
    uint8_t ecn = 0;

    uint16_t total_length = 0;
    uint16_t identification = 0;

    uint8_t flags = 0;
    uint16_t fragment_offset = 0;

    uint8_t ttl = 0;
    uint8_t protocol = 0;

    uint16_t checksum = 0;

    uint32_t src_addr = 0;
    uint32_t dst_addr = 0;
};

// ============================================================
// IPv6 header
// ============================================================

struct IPv6Header {
    uint8_t version = 0;
    uint8_t traffic_class = 0;
    uint32_t flow_label = 0;

    uint16_t payload_length = 0;
    uint8_t next_header = 0;
    uint8_t hop_limit = 0;

    uint8_t src_addr[16]{};
    uint8_t dst_addr[16]{};
};

// ============================================================
// Parsed packet
// ============================================================

struct ParsedPacket {
    bool valid = false;

    EthernetHeader ethernet;
    IPv4Header ipv4;
    IPv6Header ipv6;

    std::size_t payload_offset = 0;
    std::size_t payload_length = 0;

    std::string error;
};

// ============================================================
// PacketParser
// ============================================================

class PacketParser {
public:
    PacketParser() = default;

    ParsedPacket parse(
        const uint8_t* data,
        std::size_t length
    ) const;

private:
    bool parse_ethernet(
        const uint8_t* data,
        std::size_t length,
        EthernetHeader& ethernet,
        std::string& error
    ) const;

    bool parse_ipv4(
        const uint8_t* data,
        std::size_t length,
        IPv4Header& ipv4,
        std::size_t& payload_offset,
        std::size_t& payload_length,
        std::string& error
    ) const;

    bool parse_ipv6(
        const uint8_t* data,
        std::size_t length,
        IPv6Header& ipv6,
        std::size_t& payload_offset,
        std::size_t& payload_length,
        std::string& error
    ) const;
};

// ============================================================
// Utility functions
// ============================================================

std::string ipv4_to_string(uint32_t addr);

std::string ipv6_to_string(const uint8_t* addr);

} // namespace packet_parser

#endif // PACKET_PARSER_H