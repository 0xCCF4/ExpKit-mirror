from enum import IntEnum, auto

from expkit.base.architecture import PlatformArchitecture

from expkit.base.utils import type_checking


class PayloadType(IntEnum):
    UNKNOWN = auto()

    # Compiled executable and shared libraries
    DOTNET_DLL = auto()
    DOTNET_EXE = auto()

    NATIVE_STATIC_EXE = auto()
    NATIVE_DYNAMIC_EXE = auto()

    NATIVE_STATIC_DLL = auto()
    NATIVE_DYNAMIC_DLL = auto()

    NATIVE_SHELLCODE = auto()

    # Source code and other files
    POWERSHELL_SCRIPT = auto()
    CSHARP_PROJECT = auto()

    @staticmethod
    @type_checking
    def get_type_from_name(name: str) -> "PayloadType":
        name = name.lower()
        for value in PayloadType:
            if value.name.lower() == name:
                return value

        return PayloadType.UNKNOWN

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class Payload():
    @type_checking
    def __init__(self, type: PayloadType, platform: PlatformArchitecture, content: bytes, meta: dict = None):
        self.type = type
        self.platform = platform
        self.data = {
            "content": content,
            "meta": meta if meta is not None else {}
        }

    def __str__(self) -> str:
        return self.type.name

    def get_content(self) -> bytes:
        return self.data["content"]

    def get_content_base64(self) -> str:
        return self.data["content"].decode('base64')

    def get_content_hex(self) -> str:
        return self.data["content"].hex()

    def get_meta(self) -> dict:
        return self.data["meta"]
