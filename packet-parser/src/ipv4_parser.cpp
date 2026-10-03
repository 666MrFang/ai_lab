#include "packet_parser.h"

namespace packet_parser {

bool PacketParser::parse_ipv4(
    const uint8_t* data,
    std::size_t length,
    IPv4Header& ipv4,
    std::size_t& payload_offset,
    std::size_t& payload_length,
    std::string& error
) const
{
    constexpr std::size_t minimum_ipv4_header_length = 20;

    // --------------------------------------------------------
    // Basic length check
    // --------------------------------------------------------

    if (length < minimum_ipv4_header_length) {
        error = "packet is shorter than minimum ipv4 header";
        return false;
    }

    // --------------------------------------------------------
    // Version / IHL
    // --------------------------------------------------------

    const uint8_t version_ihl = data[0];

    ipv4.version = (version_ihl >> 4) & 0x0f;
    ipv4.ihl = version_ihl & 0x0f;

    if (ipv4.version != 4) {
        error = "invalid ipv4 version";
        return false;
    }

    if (ipv4.ihl < 5) {
        error = "invalid ipv4 ihl";
        return false;
    }

    const std::size_t header_length =
        static_cast<std::size_t>(ipv4.ihl) * 4;

    if (length < header_length) {
        error = "packet is shorter than ipv4 header";
        return false;
    }

    // --------------------------------------------------------
    // DSCP / ECN
    // --------------------------------------------------------

    ipv4.dscp = (data[1] >> 2) & 0x3f;
    ipv4.ecn = data[1] & 0x03;

    // --------------------------------------------------------
    // Total length
    // --------------------------------------------------------

    ipv4.total_length =
        static_cast<uint16_t>(data[2]) << 8 |
        static_cast<uint16_t>(data[3]);

    if (ipv4.total_length < header_length) {
        error = "invalid ipv4 total length";
        return false;
    }

    if (ipv4.total_length > length) {
        error = "ipv4 total length exceeds packet length";
        return false;
    }

    // --------------------------------------------------------
    // Identification
    // --------------------------------------------------------

    ipv4.identification =
        static_cast<uint16_t>(data[4]) << 8 |
        static_cast<uint16_t>(data[5]);

    // --------------------------------------------------------
    // Flags / Fragment offset
    // --------------------------------------------------------

    const uint16_t flags_fragment =
        static_cast<uint16_t>(data[6]) << 8 |
        static_cast<uint16_t>(data[7]);

    ipv4.flags =
        static_cast<uint8_t>((flags_fragment >> 13) & 0x07);

    ipv4.fragment_offset =
        flags_fragment & 0x1fff;

    // --------------------------------------------------------
    // TTL / Protocol
    // --------------------------------------------------------

    ipv4.ttl = data[8];
    ipv4.protocol = data[9];

    // --------------------------------------------------------
    // Header checksum
    // --------------------------------------------------------

    ipv4.checksum =
        static_cast<uint16_t>(data[10]) << 8 |
        static_cast<uint16_t>(data[11]);

    // --------------------------------------------------------
    // Source address
    // --------------------------------------------------------

    ipv4.src_addr =
        (static_cast<uint32_t>(data[12]) << 24) |
        (static_cast<uint32_t>(data[13]) << 16) |
        (static_cast<uint32_t>(data[14]) << 8) |
        static_cast<uint32_t>(data[15]);

    // --------------------------------------------------------
    // Destination address
    // --------------------------------------------------------

    ipv4.dst_addr =
        (static_cast<uint32_t>(data[16]) << 24) |
        (static_cast<uint32_t>(data[17]) << 16) |
        (static_cast<uint32_t>(data[18]) << 8) |
        static_cast<uint32_t>(data[19]);

    // --------------------------------------------------------
    // Payload
    // --------------------------------------------------------

    payload_offset = header_length;
    payload_length =
        static_cast<std::size_t>(ipv4.total_length) -
        header_length;

    return true;
}

} // namespace packet_parser