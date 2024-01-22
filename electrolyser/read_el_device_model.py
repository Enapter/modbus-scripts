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

from enum import StrEnum
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

# Register address
DEVICE_MODEL_INPUT: Final[int] = 0


class DeviceModel(StrEnum):
    """
    Values for ProjectId input register (0).
    """

    UNKNOWN = 'UNKNOWN'

    # Specific value for EL21.
    EL21 = 'EL21'

    # Specific values for EL40.
    EL40 = 'EL40'
    ES40 = 'ES40'

    # Specific value for EL41.
    ES41 = 'ES41'

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reading EL device model with Modbus'
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
        # Read ProjectId input register, address is 0. Register type is uint32,
        # so number of registers to read is 32 / 16 = 2.
        raw_device_model: list[int] = modbus_client.read_input_registers(
            reg_addr=DEVICE_MODEL_INPUT, reg_nb=2
        )

        print(f'Got raw device model data: {raw_device_model}')

        # Convert raw response to single int value with pyModbusTCP utils.
        converted_device_model: int = utils.word_list_to_long(
            val_list=raw_device_model
        )[0]

        print(f'Got converted int value: {converted_device_model}')

        # Decode converted int to human-readable device model.
        decoded_device_model: DeviceModel = DeviceModel(
            bytes.fromhex(f'{converted_device_model:x}').decode()
        )

        print(
            f'Got decoded human-readable device model: '
            f'{decoded_device_model.value}'
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
