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

from enum import IntEnum
from typing import Any, Final, Self

try:
    from pyModbusTCP import client

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
DRYER_ERRORS_INPUT: Final[int] = 6000

# Error message usually indicating that DCN is disabled
SLAVE_DEVICE_FAILURE: Final[str] = 'slave device failure'


class DryerError(IntEnum):
    """
    Enum values for bitmask of modbus dryer_errors register (6000).
    """
    UNKNOWN = -1

    TT00_INVALID_VALUE = 0
    TT01_INVALID_VALUE = 1
    TT02_INVALID_VALUE = 2
    TT03_INVALID_VALUE = 3
    TT00_VALUE_GROWTH_NOT_ENOUGH = 4
    TT01_VALUE_GROWTH_NOT_ENOUGH = 5
    TT02_VALUE_GROWTH_NOT_ENOUGH = 6
    TT03_VALUE_GROWTH_NOT_ENOUGH = 7
    PS00_TRIGGERED = 8
    PS01_TRIGGERED = 9
    F100_INVALID_RPM = 10
    F101_INVALID_RPM = 11
    F102_INVALID_RPM = 12
    PT00_INVALID_VALUE = 13
    PT01_INVALID_VALUE = 14

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reading DRY errors with Modbus'
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
        # Read dryer errors input register, address is 6000. Register type is
        # uint16, so number of registers to read is 16 / 16 = 1.
        raw_errors_data: list[int] = modbus_client.read_input_registers(
            reg_addr=DRYER_ERRORS_INPUT, reg_nb=1
        )

        print(f'Got raw dryer errors data: {raw_errors_data}')

        if errors := raw_errors_data[0]:
            # Value is not 0, converting int value to bitmask.
            bitmask: str = '{:016b}'.format(errors)[::-1]

            print(f'Got dryer errors bitmask: {bitmask}')

            decoded_errors: list[str] = [
                DryerError(bit_number).name for bit_number in [
                    index for index, bit in enumerate(bitmask) if int(bit)
                ]
            ]

            print(
                f'Got decoded errors: {", ".join(decoded_errors)}\nErrors'
                f' description is available at https://handbook.enapter.com'
            )

        else:
            # Value is 0.
            print('There are no errors')

    except Exception as e:
        # If something went wrong, we can access Modbus error/exception info.
        # For example, in case of connection problems, reading register will
        # return None and script will fail with error while data converting,
        # but real problem description will be stored in client.
        print(f'Exception occurred: {e}')
        print(f'Modbus error: {modbus_client.last_error_as_txt}')
        print(f'Modbus exception: {modbus_client.last_except_as_txt}')

        if SLAVE_DEVICE_FAILURE in modbus_client.last_except_as_txt:
            print('Please check that DCN is enabled')

        raise


if __name__ == '__main__':
    main()
