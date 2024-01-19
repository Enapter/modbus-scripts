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
import time

from enum import IntEnum
from typing import Any, Final, Self

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

# Registers addresses
REBOOT_HOLDING: Final[int] = 4
STATE_INPUT: Final[int] = 1200


class State(IntEnum):
    """
    Enum values for Electrolyser state input register (1200).
    """

    UNKNOWN = -1

    # Common states for EL2.1 and EL4.x.
    HALTED = 0
    MAINTENANCE_MODE = 1
    IDLE = 2
    STEADY = 3
    STAND_BY = 4
    CURVE = 5
    BLOWDOWN = 6

    # Specific state for EL40.
    RECOMBINER = 7

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reboot EL with Modbus'
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
        # Write reboot holding register, address is 4. Register type is
        # boolean, technically it's similar to uint16.
        modbus_client.write_single_register(
            reg_addr=REBOOT_HOLDING, reg_value=1
        )

        print('Rebooting...')

        # Reading electrolyser state input register, address is 1200. Register
        # type is enum16, technically it's similar to uint16, so number of
        # registers to read is 16 / 16 = 1. Result is None if Modbus is not
        # ready (client generates connection error, reading function returns
        # None).
        while (
            (
                state_raw_data := modbus_client.read_input_registers(
                    reg_addr=STATE_INPUT, reg_nb=1
                )
            ) is None
        ):
            print(f'Waiting for Modbus initialization...')

            time.sleep(1)

        print(
            f'Got electrolyser state {State(state_raw_data[0]).name} '
            f'after reboot'
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
