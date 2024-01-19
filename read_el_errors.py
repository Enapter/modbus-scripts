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
ERRORS_INPUT: Final[int] = 832


class Error(IntEnum):
    """
    Values for errors input register (832). Names may be used for human-readable
    description.
    """

    UNKNOWN = -1

    # Common errors for EL2.1 and EL4.x.
    INTERNAL_ERROR = 0x0FFF
    FP_01 = 0x1F81
    FP_02 = 0x1F82
    FP_03 = 0x1F83
    FP_06 = 0x1F86
    FC_10 = 0x108A
    FD_20 = 0x1114
    FR_10 = 0x118A
    FR_20 = 0x1194
    FR_50 = 0x11B2
    FR_51 = 0x11B3
    FR_52 = 0x11B4
    FR_40 = 0x11A8
    FS_01 = 0x1201
    FS_10 = 0x120A
    FT_10 = 0x128A
    ET_10 = 0x228A
    EU_10 = 0x230A
    FX_03 = 0x1403
    FX_04 = 0x1404
    FX_07 = 0x1407
    FX_11 = 0x140B
    FX_12 = 0x140C
    FX_30 = 0x141E
    FX_31 = 0x141F
    FX_33 = 0x1421
    FX_35 = 0x1423
    FX_36 = 0x1424
    FX_37 = 0x1425
    FX_38 = 0x1426
    FX_39 = 0x1427
    FF_10 = 0x148A
    FL_01 = 0x1501
    FO_30 = 0x159E

    # Specific values for EL2.1.
    EX_01 = 0x2401
    FX_02 = 0x1402
    FX_05 = 0x1405
    FX_08 = 0x1408
    FX_09 = 0x1409
    FX_10 = 0x140A
    FX_32 = 0x1420
    FX_34 = 0x1422
    FX_40 = 0x1428

    # Specific values for EL4.x.
    FX_13 = 0x140D
    FX_42 = 0x142A
    FB_10 = 0x170A
    FB_11 = 0x170B
    FB_20 = 0x1714
    FB_21 = 0x1715
    FY_10 = 0x178A
    FY_20 = 0x1794
    FY_21 = 0x1795
    FY_22 = 0x1796
    FY_23 = 0x1797
    FY_24 = 0x1798
    FY_25 = 0x1799
    FY_26 = 0x179A
    FY_27 = 0x179B
    FY_28 = 0x179C
    FY_29 = 0x179D
    FY_30 = 0x179E
    FY_31 = 0x179F
    FY_33 = 0x1721
    FY_51 = 0x17B3
    FY_52 = 0x17B4
    FY_53 = 0x17B5
    FY_54 = 0x17B6
    FY_55 = 0x17B7
    FY_56 = 0x17B8

    @classmethod
    def _missing_(cls, value: Any) -> Self:
        return cls.UNKNOWN


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reading EL errors with Modbus'
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
        # Read input register with errors array, address is 832. This register
        # has specific structure - first uint16 contains total amount of error
        # events. Number of registers to read is 528 / 16 = 33.
        raw_errors_data: list[int] = modbus_client.read_input_registers(
            reg_addr=ERRORS_INPUT, reg_nb=33
        )

        print(f'Got raw errors data: {raw_errors_data}')

        if errors_count := raw_errors_data[0]:
            # Total amount of errors is not 0.
            print(f'Got total errors count: {errors_count}')

            decoded_errors: list[str] = [
                f'{Error(error).name} ({hex(error)})' for error in
                raw_errors_data[1:errors_count + 1]
            ]

            print(
                f'Got decoded errors: {", ".join(decoded_errors)}\nErrors'
                f' description is available at https://handbook.enapter.com'
            )

        else:
            # Total amount of errors is 0.
            print('There are no errors')

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
