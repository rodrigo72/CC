import json
import struct
import utils
from jsonschema import validate


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class general_access(metaclass=SingletonMeta):
    def __init__(self):
        self._format_strings = {}

    def set_format_string(self, pdu_type, format_string):
        self._format_strings[pdu_type] = format_string

    def get_format_string(self, pdu_type):
        return self._format_strings.get(pdu_type, None)


def pdu_encode(pdu_type, data_to_send):
    match pdu_type:
        case utils.action.UPDATE.value:
            return pdu_encode_files_info(data_to_send)
        case utils.action.LEAVE.value:
            return pdu_encode_leave(data_to_send)


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

    general_access().set_format_string(utils.action.UPDATE.value, format_string)
    return struct.pack(format_string, *flat_data)


def pdu_decode(received_data):
    decoded_data = struct.unpack('!B', received_data[:1])  # all pdus have a pdu_type
    pdu_type = decoded_data[0]

    match pdu_type:
        case utils.action.UPDATE.value:
            return pdu_decode_update(received_data)
        case utils.action.LEAVE.value:
            return pdu_decode_leave(received_data)


def pdu_decode_leave(received_data):
    pass


def pdu_decode_update(received_data):
    format_string = general_access().get_format_string(utils.action.UPDATE.value)
    if not format_string:
        return None

    decoded_data = struct.unpack(format_string, received_data)
    json_data = []

    offset = 3
    number_of_files = decoded_data[1]

    for file in range(number_of_files):
        file_name = decoded_data[offset].decode("utf-8")
        n_block_sets = decoded_data[offset + 1]
        offset += 2

        blocks = []
        for _ in range(n_block_sets):
            block_size, last_block_size, n_sequences = decoded_data[offset:offset + 3]
            offset += 3

            sequences = [(decoded_data[offset + i], decoded_data[offset + i + 1]) for i in range(0, n_sequences * 2, 2)]
            offset += n_sequences * 2

            n_block_numbers = decoded_data[offset]
            offset += 1
            block_numbers = list(decoded_data[offset:offset + n_block_numbers])

            for start, end in sequences:
                block_numbers.extend(range(start, end + 1))

            block_numbers.sort()
            offset += n_block_numbers

            blocks.append({
                "size": block_size,
                "numbers": block_numbers,
                "last_block_size": last_block_size
            })

        json_data.append({
            "name": file_name,
            "blocks": blocks
        })

        offset += 1

        try:
            validate(json_data[file], utils.json_schemas_provider().get_json_schema("file_info.json"))
            print("JSON is valid against the schema.")
        except Exception as e:
            print("JSON is not valid against the schema.")
            print(e)

    return json_data


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


def pdu_encode_leave(data_to_send):
    pass


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
            "name": "panik.png",
            "blocks": [
                {
                    "size": 512,
                    "last_block_size": 21,
                    "numbers": [5, 6, 11, 12, 13, 14],
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
    data = pdu_decode_update(encoded_data)
    print(json.dumps(data, indent=4))
