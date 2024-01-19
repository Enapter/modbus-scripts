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
import random
import sys
import time

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
PRODUCTION_RATE_HOLDING: Final[int] = 1002

# Timeout after writing to somehow guarantee that value is updated
REGISTER_WRITE_TIMEOUT: Final[int] = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Writing EL production rate with Modbus'
    )

    parser.add_argument(
        '--modbus-ip', '-i', help='Modbus IP address', required=True
    )

    parser.add_argument(
        '--modbus-port', '-p', help='Modbus port', type=int, default=502
    )

    return parser.parse_args()


def _read_production_rate(modbus_client: client.ModbusClient) -> float:
    """
    Read production rate holding register, address is 1002. Register type is
    float32, so number of registers to read is 32 / 16 = 2. Convert raw
    response to single float value with pyModbusTCP utils.
    """
    return utils.decode_ieee(
        val_int=utils.word_list_to_long(
            val_list=modbus_client.read_holding_registers(
                reg_addr=PRODUCTION_RATE_HOLDING, reg_nb=2
            )
        )[0]
    )


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
        print(
            f'Got initial production rate in %: '
            f'{_read_production_rate(modbus_client=modbus_client)}'
        )

        random_production_rate: float = random.uniform(a=90.0, b=99.0)

        print(f'Generated random production rate %: {random_production_rate}')

        print('Writing new production rate...')

        # Write production rate holding register, address is 1002. Convert
        # generated float value with pyModbusTCP utils.
        modbus_client.write_multiple_registers(
            regs_addr=PRODUCTION_RATE_HOLDING,
            regs_value=utils.long_list_to_word(
                val_list=[utils.encode_ieee(val_float=random_production_rate)]
            )
        )

        time.sleep(REGISTER_WRITE_TIMEOUT)

        print(
            f'Got updated production rate in %: '
            f'{_read_production_rate(modbus_client=modbus_client)}'
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
