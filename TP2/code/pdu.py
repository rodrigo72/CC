import struct
import utils


def pdu_encode(pdu_type, data_to_send):
    match pdu_type:
        case utils.action.UPDATE.value:
            return pdu_encode_files_info(data_to_send)
        case utils.action.LEAVE.value:
            return None


def pdu_encode_response(result, counter):
    flat_data = []
    flat_data.extend([utils.action.RESPONSE.value, result, counter])
    format_string = '!BBH'
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

    return sequences + [residual]


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
