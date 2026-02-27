from systemrdl import rdltypes

from typing import Tuple
from systemrdl.rdltypes import AccessType, OnReadType, OnWriteType

# SystemRDL SW access to Opentitan swaccess field
# AccessType, OnWriteType, OnReadType, String
SW_ACCESS_MAP = [
    (AccessType.na, None,              None,            "none"), # Illegal anyways
    (AccessType.r,  None,              None,            "ro"),
    (AccessType.r,  None,              OnReadType.rclr, "rc"),
    (AccessType.rw, None,              None,            "rw"),
    (AccessType.w,  OnWriteType.woclr, None,            "r0w1c"),
    (AccessType.rw, OnWriteType.woset, None,            "rw1s"),
    (AccessType.rw, OnWriteType.woclr, None,            "rw1c"),
    (AccessType.rw, OnWriteType.wzc,   None,            "rw0c"),
    (AccessType.w,  None,              None,            "wo"),
]

def access_from_sw(
        sw: AccessType,
        onwrite: "OnWriteType|None" = None,
        onread: "OnReadType|None" = None,
        ) -> str:

    for sw_entry in SW_ACCESS_MAP:
        if sw_entry[0:3] == (sw, onwrite, onread):
            return sw_entry[3]

    assert False, f"SW access for reg cannot be mapped cannot be mapped: {sw}, {onwrite}, {onread}"

def sw_from_access(access: str) -> "Tuple[AccessType, OnWriteType, OnReadType]":
    for sw_entry in SW_ACCESS_MAP:
        if access == sw_entry[3]:
            return sw_entry[0], sw_entry[1], sw_entry[2]

    assert False, f"OpenTitan property: {access}, not supported"


# SystemRDL HW access to Opentitan hwaccess field
# AccessType, String
HW_ACCESS_MAP = [
    (AccessType.na, None, "none"),
    (AccessType.r,  None, "hro"),
    (AccessType.rw, True, "hrw"),
    (AccessType.w,  True, "hwo"),
]

def access_from_hw(hw: AccessType) -> str:

    for hw_entry in HW_ACCESS_MAP:
        if hw_entry[0] == hw:
            return hw_entry[1]

    assert False, f"HW access for reg cannot be mapped: {hw}"

def hw_from_access(access: str) -> "AccessType":
    for hw_entry in HW_ACCESS_MAP:
        if access == hw_entry[2]:
            return hw_entry[0], hw_entry[1]

    assert False, f"OpenTitan property: {access}, not supported"

