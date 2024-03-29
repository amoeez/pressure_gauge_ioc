import datetime
import logging
import socket
import struct
import sys

from caproto import ChannelData
from caproto.server import (
    AsyncLibraryLayer,
    PVGroup,
    pvproperty,
    PvpropertyString,
    run,
    template_arg_parser,
)


def pressure_read(address, port):
    """
    Communicates with the pressure guage
    """

    message = message_generator()

    sock = connection(address, port)

    sock.sendall(message)

    message_received = sock.recv(1024)

    sock.close()

    message_verification = check_crc(message_received)

    if message_verification:

        pressure_read_slice = message_received[9:-2]

        pressure_read_hex_values = [item for item in pressure_read_slice]

        pressure_reading = (
            (pressure_read_hex_values[0] << 24)
            | (pressure_read_hex_values[1] << 16)
            | (pressure_read_hex_values[2] << 8)
            | pressure_read_hex_values[3] << 0
        )

        pressure_reading = pressure_reading / (2**20)
    else:
        print("Pressure reading failed")

    return pressure_reading


def check_crc(message):
    """ """
    message_sans_crc = []

    for i in range(len(message) - 2):
        message_sans_crc.append(message[i])

    crc16_table = crc16_table()

    crc_calc = inficon_crc16(
        message_sans_crc, len(message_sans_crc), inficon_init_crc16_table()
    )

    message_w_crc_calc = struct.pack("<13BH", *message_sans_crc, crc_calc)

    if message_w_crc_calc == message:
        return True
    else:
        return False


def message_generator():
    """
    generates message with crc

    """
    message = []

    message.append(0)
    message.append(0)
    message.append(0)
    message.append(5)
    message.append(1)
    message.append(0)
    message.append(221)
    message.append(0)
    message.append(0)

    message_hex = struct.pack("9B", *message)

    crc = inficon_crc16(message_hex, len(message), inficon_init_crc16_table())

    # crc_1 = (crc >> 8) & 0xFF
    # crc_2 = crc & 0xFF

    # message.append(crc_2) # flipping the high  & low bytes
    # message.append(crc_1)

    message_string = struct.pack("<9BH", *message, crc)

    # for item in message:
    #     message_string += '\\'+ hex(item)[1:]

    return message_string


def inficon_init_crc16_table():
    """
    Code to generate crc16 table
    """

    polynomial = 0x8408
    _inficon_crc16_table = [0] * 256

    for i in range(256):
        value = 0
        temp = i

        for j in range(8):
            if (value ^ temp) & 0x0001:
                value = (value >> 1) ^ polynomial
            else:
                value >>= 1
            temp >>= 1

        _inficon_crc16_table[i] = value & 0xFFFF

    return _inficon_crc16_table


def inficon_crc16(data, length, crc16_table):
    """
    generates the crc16 code

    """
    initial = 0xFFFF
    crc = initial

    for i in range(length):

        crc = (crc16_table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8)) & 0xFFFF

    return crc


def connection(address, port):
    """
    for now pressure guage address and host is hard-coded
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock.setblocking(False)

    sock.connect((address, port))

    return sock


class PressureIOC(PVGroup):
    """
    A group of PVs regarding reading the pressure.
    """

    def __init__(self, address, port, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.address: str = address
        self.port: str = port

    timestamp = pvproperty(
        value=str(datetime.datetime.utcnow().isoformat() + "Z"),
        name="timestamp",
        doc="Timestamp of pressure measurement",
        dtype=PvpropertyString,
    )

    # @date.scan(period=6)    # every ten minutes
    # async def date(self, instance: ChannelData, async_lib: AsyncLibraryLayer):
    #     await self.date.write(value=str(datetime.date.today()))

    pressure = pvproperty(value=0.0, name="pressure", units="mbar")

    @pressure.scan(period=6)
    async def pressure(self, instance: ChannelData, async_lib: AsyncLibraryLayer):
        address = self.address
        port = self.port
        await self.pressure.write(pressure_read(address, port))
        await self.timestamp.write(datetime.datetime.utcnow().isoformat() + "Z")


def main(args=None):

    parser, split_args = template_arg_parser(
        default_prefix="Pressure:",
        desc="EPICS IOC for Inficon Pressure Gauge PCG550! It outputs the pressure in mbar",
    )

    if args is None:
        args = sys.argv[1:]

    # parser = argparse.ArgumentParser(description="EPICS IOC for Inficon Pressure \
    #                                 Gauge PCG550! It outputs the pressure in mbar")
    parser.add_argument(
        "--host", required=True, type=str, help="IP address of the host/device"
    )
    parser.add_argument(
        "--port", required=True, type=int, help="Port number of the device"
    )

    args = parser.parse_args()

    logging.info("Running pressure gauge IOC")

    # address = args.address
    # port = args.port

    ioc_options, run_options = split_args(args)

    ioc = PressureIOC(address=args.host, port=args.port, **ioc_options)
    run(ioc.pvdb, **run_options)


if __name__ == "__main__":

    main()
