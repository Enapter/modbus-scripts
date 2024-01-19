# Copyright 2024 Enapter
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import sys
import uuid

from typing import Final

try:
    from pyModbusTCP import client, utils

except ImportError:
    print(
        'No pyModbusTCP module installed.\n.'
        '1. Create virtual environment\n'
        '2. Run \'pip install pyModbusTCP==0.2.1\''
    )

    raise


# Supported Python version
MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 10)

# Register address
CONTROL_BOARD_SERIAL_INPUT: Final[int] = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reading EL control board serial with Modbus'
    )

    parser.add_argument(
        '--modbus-ip', '-i', help='Modbus IP address', required=True
    )

    parser.add_argument(
        '--modbus-port', '-p', help='Modbus port', type=int, default=502
    )

    return parser.parse_args()


def main() -> None:
    if sys.version_info < MIN_PYTHON_VERSION:
        raise RuntimeError(
            f'Python version >='
            f' {".".join(str(version) for version in MIN_PYTHON_VERSION)} is'
            f' required'
        )

    args: argparse.Namespace = parse_args()

    modbus_client: client.ModbusClient = client.ModbusClient(
        host=args.modbus_ip, port=args.modbus_port
    )

    try:
        # Read control board serial input register, address is 6. Register type
        # is uint128, so number of registers to read is 128 / 16 = 8.
        raw_board_serial: list[int] = modbus_client.read_input_registers(
            reg_addr=CONTROL_BOARD_SERIAL_INPUT, reg_nb=8
        )

        print(f'Got raw control board serial data: {raw_board_serial}')

        # Convert raw response to single int value. pyModbusTCP utils has no
        # built-in method for uint128, combining with 'manual' conversion.
        long_long_list: list[int] = utils.word_list_to_long(
            val_list=raw_board_serial, long_long=True
        )

        converted_board_serial: int = (
            long_long_list[0] << 64 | long_long_list[1]
        )

        print(
            f'Got converted int value: {converted_board_serial}'
        )

        # Decode converted int to human-readable mainboard id which in fact is
        # string representation of UUID.
        decoded_board_serial: str = str(
            uuid.UUID(int=converted_board_serial)
        ).upper()

        print(
            f'Got decoded human-readable serial number: {decoded_board_serial}'
        )

    except Exception as e:
        # If something went wrong, we can access Modbus error/exception info.
        # For example, in case of connection problems, reading register will
        # return None and script will fail with error while data converting,
        # but real problem description will be stored in client.
        print(f'Exception occurred: {e}')
        print(f'Modbus error: {modbus_client.last_error_as_txt}')
        print(f'Modbus exception: {modbus_client.last_except_as_txt}')

        raise


if __name__ == '__main__':
    main()
