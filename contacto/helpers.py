from enum import IntEnum

class DType(IntEnum):
    TEXT  = 1,
    BIN   = 2,
    AXREF = 3,
    EXREF = 4

def bytes_to_attrdata(dtype, bin_data):
    if dtype is DType.BIN:
        return bin_data
    if dtype is DType.TEXT:
        return bin_data.decode('utf-8')
    return int.from_bytes(bin_data, byteorder='little')

def attrdata_to_bytes(dtype, attr_data):
    if dtype is DType.BIN:
        return attr_data
    if dtype is DType.TEXT:
        return attr_data.encode('utf-8')
    return attr_data.id.to_bytes(4, byteorder='little')
