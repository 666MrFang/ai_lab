def calculate_checksum(data):
    result = 0

    for value in data:
        result += value

    return result & 0xffff