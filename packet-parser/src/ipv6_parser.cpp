#include "packet_parser.h"

#include <sstream>

namespace packet_parser {

bool PacketParser::parse_ipv6(
    const uint8_t* data,
    std::size_t length,
    IPv6Header& ipv6,
    std::size_t& payload_offset,
    std::size_t& payload_length,
    std::string& error
) const
{
    constexpr std::size_t minimum_ipv6_header_length = 40;

    // --------------------------------------------------------
    // Basic length check
    // --------------------------------------------------------

    if (length < minimum_ipv6_header_length) {
        error = "packet is shorter than minimum ipv6 header";
        return false;
    }

    // --------------------------------------------------------
    // Version / Traffic class / Flow label
    // --------------------------------------------------------

    ipv6.version = (data[0] >> 4) & 0x0f;

    if (ipv6.version != 6) {
        error = "invalid ipv6 version";
        return false;
    }

    ipv6.traffic_class =
        static_cast<uint8_t>((data[0] & 0x0f) << 4) |
        static_cast<uint8_t>((data[1] >> 4) & 0x0f);

    ipv6.flow_label =
        (static_cast<uint32_t>(data[1] & 0x0f) << 16) |
        (static_cast<uint32_t>(data[2]) << 8) |
        static_cast<uint32_t>(data[3]);

    // --------------------------------------------------------
    // Payload length
    // --------------------------------------------------------

    ipv6.payload_length =
        static_cast<uint16_t>(data[4]) << 8 |
        static_cast<uint16_t>(data[5]);

    // --------------------------------------------------------
    // Next header / Hop limit
    // --------------------------------------------------------

    ipv6.next_header = data[6];
    ipv6.hop_limit = data[7];

    // --------------------------------------------------------
    // Source address
    // --------------------------------------------------------

    for (std::size_t i = 0; i < 16; ++i) {
        ipv6.src_addr[i] = data[8 + i];
    }

    // --------------------------------------------------------
    // Destination address
    // --------------------------------------------------------

    for (std::size_t i = 0; i < 16; ++i) {
        ipv6.dst_addr[i] = data[24 + i];
    }

    // --------------------------------------------------------
    // Payload
    // --------------------------------------------------------

    payload_offset = minimum_ipv6_header_length;

    if (ipv6.payload_length > length - minimum_ipv6_header_length) {
        error = "ipv6 payload length exceeds packet length";
        return false;
    }

    payload_length = ipv6.payload_length;

    return true;
}

std::string ipv6_to_string(const uint8_t* addr)
{
    uint16_t groups[8];

    for (std::size_t i = 0; i < 8; ++i) {
        groups[i] =
            static_cast<uint16_t>(addr[i * 2]) << 8 |
            static_cast<uint16_t>(addr[i * 2 + 1]);
    }

    std::size_t best_start = 8;
    std::size_t best_length = 0;

    for (std::size_t i = 0; i < 8; ++i) {
        if (groups[i] != 0) {
            continue;
        }

        std::size_t run_length = 0;

        while (i + run_length < 8 && groups[i + run_length] == 0) {
            ++run_length;
        }

        if (run_length > best_length) {
            best_length = run_length;
            best_start = i;
        }

        i += run_length - 1;
    }

    std::ostringstream stream;

    stream << std::hex;

    bool first = true;
    bool after_compression = false;

    for (std::size_t i = 0; i < 8; ++i) {
        if (best_length >= 2 && i == best_start) {
            stream << "::";

            first = false;
            after_compression = true;

            i += best_length - 1;
            continue;
        }

        if (!first && !after_compression) {
            stream << ":";
        }

        stream << groups[i];

        first = false;
        after_compression = false;
    }

    return stream.str();
}

} // namespace packet_parser
