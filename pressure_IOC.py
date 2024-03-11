from caproto import ChannelData, ChannelType
from caproto.server import (AsyncLibraryLayer, PVGroup, SubGroup, pvproperty, PvpropertyString,
                            ioc_arg_parser, run, PvpropertyInteger)

import socket
import datetime
import struct
# from read import pressure_read

import socket
import struct


def pressure_read():
    '''
    Communicates with the pressure guage
    '''
 
    message = message_generator()

    sock = connection()

    sock.sendall(message.encode())

    message_received = sock.recv(1024)

    sock.close()

    pressure_reading = (message_received[3] << 0) | (message_received[2] << 8) | \
    (message_received[1] << 16) | (message_received[0] << 24)

    pressure_reading = pressure_reading/ (2**20)

    return pressure_reading


def message_generator():
    '''
    generates message with crc

    '''
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
    
    message_hex = struct.pack('9B', *message)

    crc = inficon_crc16(message_hex, len(message),
                        inficon_init_crc16_table())
    
    crc_1 = (crc >> 8) & 0xFF
    crc_2 = crc & 0xFF

    message.append(crc_2) # flipping the high  & low bytes
    message.append(crc_1)
    
    message_string = ''

    for item in message:
        message_string += '\\'+ hex(item)[1:]

    return message_string


def inficon_init_crc16_table():
    '''
    Code to generate crc16 table
    '''
    
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
    '''
    generates the crc16 code

    '''
    initial = 0xFFFF
    crc = initial
    
    for i in range(length):

        crc = (crc16_table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8)) & 0xFFFF

    return crc


def connection(address = '172.17.1.14', host=4012):
    '''
    for now pressure guage address and host is hard-coded
    '''

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)

    sock.connect((address, host))

    return sock



class PressureIOC(PVGroup):
    """
    A group of PVs regarding reading the pressure. 
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    timestamp = pvproperty(
        value=str(datetime.datetime.utcnow().isoformat() + 'Z'),
        name="timestamp",
        doc="Timestamp of pressure measurement",
        dtype=PvpropertyString,
        )

    # @date.scan(period=6)    # every ten minutes
    # async def date(self, instance: ChannelData, async_lib: AsyncLibraryLayer):
    #     await self.date.write(value=str(datetime.date.today()))

    pressure = pvproperty(
        value = 0.0,
        name="pressure",
        units="mbar"
    )

    @pressure.scan(period=6)
    async def pressure(self, instance: ChannelData, async_lib: AsyncLibraryLayer):
        await self.pressure.write(pressure_read())
        await self.timestamp.write(datetime.datetime.utcnow().isoformat() + 'Z')


if __name__ == '__main__':

    ioc_options, run_options = ioc_arg_parser(
        default_prefix="pressure:", desc="Pressure sensor")
    
    ioc = PressureIOC(**ioc_options)
    run(ioc.pvdb, **run_options)

    
