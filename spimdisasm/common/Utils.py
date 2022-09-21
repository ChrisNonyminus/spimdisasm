#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Decompollaborate
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import csv
import os
import hashlib
import json
import rabbitizer
import struct
import subprocess
import sys

from .GlobalConfig import GlobalConfig, InputEndian


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def printQuietless(*args, **kwargs):
    if not GlobalConfig.QUIET:
        print(*args, **kwargs)

def epprintQuietless(*args, **kwargs):
    if not GlobalConfig.QUIET:
        print(*args, file=sys.stderr, **kwargs)


def printVerbose(*args, **kwargs):
    if not GlobalConfig.QUIET and GlobalConfig.VERBOSE:
        print(*args, **kwargs)

def eprintVerbose(*args, **kwargs):
    if not GlobalConfig.QUIET and GlobalConfig.VERBOSE:
        print(*args, file=sys.stderr, **kwargs)

# https://stackoverflow.com/questions/1512457/determining-if-stdout-for-a-python-process-is-redirected
def isStdoutRedirected() -> bool:
    return not sys.stdout.isatty()

# Returns the md5 hash of a bytearray
def getStrHash(byte_array: bytearray) -> str:
    return str(hashlib.md5(byte_array).hexdigest())

def writeBytearrayToFile(filepath: str, array_of_bytes: bytearray):
    with open(filepath, mode="wb") as f:
        f.write(array_of_bytes)

def readFileAsBytearray(filepath: str) -> bytearray:
    if not os.path.exists(filepath):
        return bytearray(0)
    with open(filepath, mode="rb") as f:
        return bytearray(f.read())

def readFile(filepath: str) -> list[str]:
    with open(filepath) as f:
        return [x.strip() for x in f.readlines()]

def readJson(filepath):
    with open(filepath) as f:
        return json.load(f)

def removeExtraWhitespace(line: str) -> str:
    return " ".join(line.split())

def bytesToWords(array_of_bytes: bytearray, offset: int=0, offsetEnd: int|None=None) -> list[int]:
    totalBytesCount = len(array_of_bytes)
    if totalBytesCount == 0:
        return list()

    bytesCount = totalBytesCount
    if offsetEnd is not None and offsetEnd > 0:
        bytesCount = offsetEnd
    bytesCount -= offset

    if GlobalConfig.ENDIAN == InputEndian.MIDDLE:
        # Convert middle endian to big endian
        halfwords = bytesCount//2
        little_byte_format = f"<{halfwords}H"
        big_byte_format = f">{halfwords}H"
        tmp = struct.unpack_from(little_byte_format, array_of_bytes, offset)
        struct.pack_into(big_byte_format, array_of_bytes, offset, *tmp)

    words = bytesCount//4
    endian_format = f">{words}I"
    if GlobalConfig.ENDIAN == InputEndian.LITTLE:
        endian_format = f"<{words}I"
    return list(struct.unpack_from(endian_format, array_of_bytes, offset))

#! deprecated
bytesToBEWords = bytesToWords

def wordsToBytes(words_list: list[int], buffer: bytearray) -> bytearray:
    if GlobalConfig.ENDIAN == InputEndian.MIDDLE:
        raise BufferError("TODO: wordsToBytes: GlobalConfig.ENDIAN == InputEndian.MIDDLE")

    words = len(words_list)
    endian_format = f">{words}I"
    if GlobalConfig.ENDIAN == InputEndian.LITTLE:
        endian_format = f"<{words}I"
    struct.pack_into(endian_format, buffer, 0, *words_list)
    return buffer

#! deprecated
beWordsToBytes = wordsToBytes

def wordToFloat(word: int) -> float:
    return struct.unpack('>f', struct.pack('>I', word))[0]

def qwordToDouble(qword: int) -> float:
    return struct.unpack('>d', struct.pack('>Q', qword))[0]

def wordToCurrenEndian(word: int) -> int:
    if GlobalConfig.ENDIAN == InputEndian.BIG:
        return word

    if GlobalConfig.ENDIAN == InputEndian.LITTLE:
        return struct.unpack('<I', struct.pack('>I', word))[0]

    # MIDDLE
    first, second = struct.unpack('>2H', struct.pack('<2H', word >> 16, word & 0xFFFF))
    return (first << 16) | second

def runCommandGetOutput(command: str, args: list[str]) -> list[str] | None:
    try:
        output = subprocess.check_output([command, *args]).decode("utf-8")
        return output.strip().split("\n")
    except:
        return None

def readCsv(filepath: str) -> list[list[str]]:
    data: list[list[str]] = []
    with open(filepath) as f:
        lines = f.readlines()
        processedLines = [x.strip().split("#")[0] for x in lines]
        csvReader = csv.reader(processedLines)
        for row in csvReader:
            data.append(list(row))

    return data

# Escape characters that are unlikely to be used
bannedEscapeCharacters = {
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    # 0x07, # '\a'
    0x08, # '\b'
    # 0x09, # '\t'
    # 0x0A, # '\n'
    0x0B, # '\v'
    # 0x0C, # '\f'
    # 0x0D, # '\r'
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
    0x14,
    0x15,
    0x16,
    0x17,
    0x18,
    0x19,
    0x1A,
    # 0x1B, # VT escape sequences
    0x1C,
    0x1D,
    0x1E,
    0x1F,
}

escapeCharactersSpecialCases = {0x1B, 0x8C, 0x8D}

def decodeString(buf: bytearray, offset: int) -> tuple[list[str], int]:
    result = []

    dst = bytearray()
    i = 0
    while offset + i < len(buf) and buf[offset + i] != 0:
        char = buf[offset + i]
        if char in bannedEscapeCharacters:
            raise RuntimeError()
        elif char in escapeCharactersSpecialCases:
            if dst:
                decoded = rabbitizer.Utils.escapeString(dst.decode("EUC-JP"))
                result.append(decoded)
                dst.clear()
            result.append(f"\\x{char:02X}")
        else:
            dst.append(char)
        i += 1

    if offset + i > len(buf):
        raise RuntimeError("Reached the end of the buffer without finding an 0")

    if dst:
        decoded = rabbitizer.Utils.escapeString(dst.decode("EUC-JP"))
        result.append(decoded)
    return result, i


# Copied from argparse.py to be able to use it on Python versions < 3.9
class BooleanOptionalAction(argparse.Action):
    def __init__(self,
                 option_strings,
                 dest,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):

        _option_strings = []
        for option_string in option_strings:
            _option_strings.append(option_string)

            if option_string.startswith('--'):
                option_string = '--no-' + option_string[2:]
                _option_strings.append(option_string)

        if help is not None and default is not None:
            help += " (default: %(default)s)"

        super().__init__(
            option_strings=_option_strings,
            dest=dest,
            nargs=0,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string: str|None=None):
        if option_string is not None and option_string in self.option_strings:
            setattr(namespace, self.dest, not option_string.startswith('--no-'))

    def format_usage(self):
        return ' | '.join(self.option_strings)
