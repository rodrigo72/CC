import struct
import utils
import socket
from typing import List, Union


def pdu_encode(pdu_type, data_to_send):
    match pdu_type:
        case utils.action.UPDATE.value:
            return pdu_encode_files_info(data_to_send)
        case utils.action.LOCATE.value:
            return pdu_encode_locate(data_to_send)
        case _:
            return None


def pdu_encode_locate(data_to_send):
    file_name = data_to_send.encode("utf-8")
    file_name_len = len(file_name)
    return struct.pack('!BB%ds' % file_name_len,
                       utils.action.LOCATE.value, file_name_len, file_name)


def pdu_encode_response(result, counter):
    flat_data = []
    flat_data.extend([utils.action.RESPONSE.value, result, counter])
    format_string = '!BBH'
    return struct.pack(format_string, *flat_data)


def pdu_encode_locate_response(addresses, result1, result2, counter):
    addresses_dict = {}
    for address in addresses:
        addresses_dict[address[1]] = address[0]

    print(result1, result2, "\n\n")

    ip_block_size_dict = {}
    ip_last_block_size_dict = {}

    for block_size, block_numbers_str, ip_address in result1:
        block_numbers = list(map(int, block_numbers_str.split(',')))
        ip_block_size_dict.setdefault(ip_address, {}).setdefault(block_size, []).extend(block_numbers)

    for last_block_size, block_numbers_str, ip_address in result2:
        block_number, original_division_size = list(map(int, block_numbers_str.split(',')))
        ip_last_block_size_dict.setdefault(ip_address, {})[original_division_size] = (block_number, last_block_size)

    print(ip_block_size_dict)
    print(ip_last_block_size_dict)

    number_of_ips = len(ip_block_size_dict.keys())

    format_string = '!BHH'
    flat_data = [utils.action.RESPONSE_LOCATE.value, counter, number_of_ips]

    for ip_address, block_size_dict in ip_block_size_dict.items():

        block_size_dict_len = len(block_size_dict.keys())
        format_string += 'BBBB'
        flat_data.extend(socket.inet_aton(ip_address))
        format_string += 'H'
        flat_data.extend([block_size_dict_len])

        for block_size, block_numbers in block_size_dict.items():

            last_block_size = 0
            block_number = None
            if ip_address in ip_last_block_size_dict:
                if block_size in ip_last_block_size_dict[ip_address]:
                    block_number, last_block_size = ip_last_block_size_dict[ip_address][block_size]

            print(block_numbers)
            sequences = get_sequences(block_numbers)
            sequences, residual = sequences[:-1], sequences[-1]
            if last_block_size != 0:
                residual.append(block_number)

            n_sequences = len(sequences)
            n_residual = len(residual)

            print(sequences, residual, "\n\n")

            format_string += 'HHH'
            flat_data.extend([block_size, last_block_size, n_sequences])

            for sequence in sequences:
                format_string += 'HH'
                flat_data.extend(sequence)

            format_string += 'H'
            flat_data.extend([n_residual])

            format_string += 'H' * n_residual
            flat_data.extend(residual)

    print(flat_data)
    return struct.pack(format_string, *flat_data)


def pdu_encode_files_info(files_infos):
    format_string = '!BB'
    flat_data = [utils.action.UPDATE.value, len(files_infos)]

    for file_info in files_infos:
        file_name = file_info["name"].encode("utf-8")
        file_name_len = len(file_name)
        n_block_sets = len(file_info["blocks"])

        format_string += 'B%dsB' % file_name_len
        flat_data.extend([file_name_len, file_name, n_block_sets])

        for block_set in file_info["blocks"]:
            block_size = block_set["size"]
            last_block_size = block_set["last_block_size"]

            result = get_sequences(block_set["numbers"])
            n_seq = len(result) - 1  # last sequence is residual

            format_string += 'HHB'
            flat_data.extend([block_size, last_block_size, n_seq])

            for sequence in result[:-1]:
                format_string += 'HH'
                flat_data.extend(sequence)

            residual = result[-1]
            n_residual = len(residual)

            format_string += 'H'
            flat_data.extend([n_residual])

            format_string += 'H' * n_residual
            flat_data.extend(residual)

    return struct.pack(format_string, *flat_data)


def get_sequences(block_numbers):
    sequences = []
    current_sequence = []
    residual = []

    for num in sorted(set(block_numbers)):
        if not current_sequence or num == current_sequence[-1] + 1:
            current_sequence.append(num)
        else:
            if len(current_sequence) > 3:
                sequences.append([current_sequence[0], current_sequence[-1]])
            else:
                residual.extend(current_sequence)
            current_sequence = [num]

    if len(current_sequence) > 3:
        sequences.append([current_sequence[0], current_sequence[-1]])
    else:
        residual.extend(current_sequence)

    sequences += [residual]
    return sequences


# for testing purposes
if __name__ == "__main__":
    files_info = [
        {
            "name": "belo.png",
            "blocks": [
                {
                    "size": 1024,
                    "last_block_size": 210,
                    "numbers": [3, 4, 5, 6, 9, 10, 11, 12, 13],
                },
                {
                    "size": 2048,
                    "last_block_size": 1021,
                    "numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 14, 20],
                }
            ],
        },
        {
            "name": "java.png",
            "blocks": [
                {
                    "size": 1024,
                    "last_block_size": 21,
                    "numbers": [20, 21, 22, 23, 24, 25, 40, 10]
                }
            ]
        }
    ]

    encoded_data = pdu_encode_files_info(files_info)
