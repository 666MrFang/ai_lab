#include "packet_parser.h"

#include <sstream>

namespace packet_parser {

ParsedPacket PacketParser::parse(
    const uint8_t* data,
    std::size_t length
) const
{
    ParsedPacket packet;

    if (length == 0) {
        packet.error = "input packet is empty";
        return packet;
    }

    if (data == nullptr) {
        packet.error = "input data is null";
        return packet;
    }

    // --------------------------------------------------------
    // Parse Ethernet header
    // --------------------------------------------------------

    if (!parse_ethernet(
            data,
            length,
            packet.ethernet,
            packet.error)) {
        return packet;
    }

    // --------------------------------------------------------
    // Check Ethernet protocol
    // --------------------------------------------------------

    const std::size_t ip_offset = 14;

    if (packet.ethernet.ether_type == ETHERTYPE_IPV4) {
        // ----------------------------------------------------
        // Parse IPv4 header
        // ----------------------------------------------------

        if (!parse_ipv4(
                data + ip_offset,
                length - ip_offset,
                packet.ipv4,
                packet.payload_offset,
                packet.payload_length,
                packet.error)) {
            return packet;
        }
    } else if (packet.ethernet.ether_type == ETHERTYPE_IPV6) {
        // ----------------------------------------------------
        // Parse IPv6 header
        // ----------------------------------------------------

        if (!parse_ipv6(
                data + ip_offset,
                length - ip_offset,
                packet.ipv6,
                packet.payload_offset,
                packet.payload_length,
                packet.error)) {
            return packet;
        }
    } else {
        packet.error = "unsupported ethernet protocol";
        return packet;
    }

    // payload_offset is relative to the IP header.
    packet.payload_offset += ip_offset;

    packet.valid = true;

    return packet;
}

bool PacketParser::parse_ethernet(
    const uint8_t* data,
    std::size_t length,
    EthernetHeader& ethernet,
    std::string& error
) const
{
    constexpr std::size_t ethernet_header_length = 14;

    if (length < ethernet_header_length) {
        error = "packet is shorter than ethernet header";
        return false;
    }

    // Destination MAC
    for (std::size_t i = 0; i < 6; ++i) {
        ethernet.dst_mac[i] = data[i];
    }

    // Source MAC
    for (std::size_t i = 0; i < 6; ++i) {
        ethernet.src_mac[i] = data[6 + i];
    }

    // Ethernet type
    ethernet.ether_type =
        static_cast<uint16_t>(data[12]) << 8 |
        static_cast<uint16_t>(data[13]);

    return true;
}

std::string ipv4_to_string(uint32_t addr)
{
    std::ostringstream stream;

    stream
        << ((addr >> 24) & 0xff) << "."
        << ((addr >> 16) & 0xff) << "."
        << ((addr >> 8) & 0xff) << "."
        << (addr & 0xff);

    return stream.str();
}

} // namespace packet_parser