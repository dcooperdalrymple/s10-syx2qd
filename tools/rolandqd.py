#!/usr/bin/env python3
# vim:fileencoding=ISO-8859-1
#
# Title: Roland QuickDisk Encoder/Decoder
# Description: Works with Roland QD floppy data in *.qd format
# Author: D Cooper Dalrymple (https://dcdalrymple.com/)
# Created: 2021-10-13
#
# Requires Python 3.0 or later

try:
    import sys
    import math
    import argparse
    from os import path
    import struct
except ImportError as err:
    print("Could not load {} module.".format(err))
    raise SystemExit

class Utilities:

    def printhex(data):
        for i in range(len(data)):
            print("0x{:02x}".format(data[i]), end="")
            if i != len(data)-1:
                print(",", end="")
                if i%8 == 7:
                    print()
                else:
                    print(" ", end="")
        print()

    def printbin(data):
        for i in range(len(data)):
            print("{:08b}".format(data[i]), end="")
        print()

    def process(data, mode, verbose=0, args=False):
        block = 0
        if args and args.block > 0:
            block = args.block

        if type(mode) is str:
            mode = [mode]

        for i in range(len(mode)):
            if mode[i] == "mfm-encode":
                data = MFM.bintomfm(data)
            elif mode[i] == "mfm-decode":
                data = MFM.mfmtobin(data)
            elif mode[i] == "mfm-sync":
                data = MFM.sync(data, verbose, block)
            elif mode[i] == "lut-invert":
                data = LUT.invert(data)
            elif mode[i] == "qd-generate":
                data = QD.generate(verbose)
            elif mode[i] == "crc-check":
                data = CRC.check(data, verbose) # CRC value (uint16_t)

        return data

    def getext(mode):
        if type(mode) is list:
            mode = mode[-1]

        if mode == "mfm-encode":
            return "mfm"
        elif mode == "mfm-decode":
            return "bin"
        elif mode == "lut-invert":
            return "inv"
        elif mode == "qd-generate" or "qd-write":
            return "qd"
        else:
            return "bin"

    def getbit(data, bit_offset):
        return (input[bit_offset>>3] >> (0x07-(bit_offset&0x07))) & 0x01

    def setbit(data, bit_offset, state):
        if state:
            data[bit_offset>>3] = data[bit_offset>>3] | (0x80 >> (bit_offset&0x07))
        else:
            data[bit_offset>>3] = data[bit_offset>>3] & ~(0x80 >> (bit_offset&0x07))

class MFM:

    BUFFER_SIZE = 10*1024

    mfmsyncword = [
        0x94, 0x4A, 0x94, 0x4A, 0x94, 0x4A, 0x94, 0x4A,
        0x94, 0x4A, 0x94, 0x4A, 0x94, 0x4A, 0x44, 0x91
    ]

    binsyncword = [
        0x16, 0x16, 0x16, 0x16, 0x16, 0x16, 0x16, 0xa5
    ]

    binsyncend = [
        16, 16, 16, 16, 16, 16, 16
    ]

    def mfmtobin(input):
        input_size = len(input)<<3

        output = [0 for i in range(MFM.BUFFER_SIZE)]
        output_size = len(output)<<3

        i = 0
        b = 0x80
        bit_offset = 0
        byte = 0

        while True:
            byte = input[bit_offset>>3]
            c1 = byte & (0x80>>(bit_offset&0x07))
            bit_offset += 1

            byte = 0
            if bit_offset < input_size:
                byte = input[bit_offset>>3]
            c2 = byte & (0x80>>(bit_offset&0x07))
            bit_offset += 1

            if not c1 and c2:
                output[i] = output[i] | b
            else:
                output[i] = output[i] & ~b

            b = b>>1
            if not b:
                b = 0x80
                i += 1

            if i >= len(output) or bit_offset >= input_size:
                break

        # Clean up output buffer size
        output = output[:i]

        return output

    def bintomfm(input):
        input_size = len(input)<<3 # all the bits!

        output = [0 for i in range(MFM.BUFFER_SIZE)]
        output_size = len(output)<<3

        i = 0
        b = 0x80
        bit_offset = 0
        lastbit = 0

        while True:

            if input[i] & b:
                Utilities.setbit(output, bit_offset, 0)
                bit_offset = (bit_offset+1)%output_size
                Utilities.setbit(output, bit_offset, 1)
                bit_offset = (bit_offset+1)%output_size
                lastbit = 1
            else:
                if lastbit:
                    Utilities.setbit(output, bit_offset, 0)
                    bit_offset = (bit_offset+1)%output_size
                    Utilities.setbit(output, bit_offset, 0)
                    bit_offset = (bit_offset+1)%output_size
                else:
                    Utilities.setbit(output, bit_offset, 1)
                    bit_offset = (bit_offset+1)%output_size
                    Utilities.setbit(output, bit_offset, 0)
                    bit_offset = (bit_offset+1)%output_size
                lastbit = 0

            b = b>>1
            if not b:
                b = 0x80
                i += 1

            if i >= len(input):
                break

        # Clean up output buffer size
        output = output[:(bit_offset>>3)]

        return output

    def sync(input, verbose, block=1, word=False):
        if word == False:
            word = MFM.mfmsyncword

        bit_offset = 0
        for i in range(block):
            bit_offset = MFM.searchbits(input, MFM.mfmsyncword)
            print("Block: {}; Sync: {};".format(i, bit_offset))
            if not bit_offset:
                return input

            input = MFM.offset(input, bit_offset)
            if i < block-1:
                input = MFM.offset(input, 1)

        if verbose:
            print("Sync Bit Offset: {}".format(bit_offset))

        return input

    def searchbits(data, word):
        data_size = len(data)<<3
        word_size = len(word)<<3

        # Apply all 8 bit offsets to search word
        searchwords = [[0 for j in range(len(word)+1)] for i in range(8)]
        for i in range(8):
            prev = 0
            for j in range(len(word)):
                searchwords[i][j] = prev | ((word[j]>>i)&0xff)
                prev = (word[j]<<(8-i))&0xff
            searchwords[i][len(word)] = prev

        searchindex = 0
        while searchindex < len(data)-len(word):
            for i in range(8): # i = bit offset
                j = 1 # j = number of bytes that match up
                while j < len(word) and not (searchwords[i][j] ^ data[searchindex + j]):
                    j += 1

                #print("Byte: {}; Bit: {}; Found: {};".format(searchindex, i, j))

                if j == len(word): # all the bytes were matched up for this bit offset
                    if not ((searchwords[i][0] ^ data[searchindex]) & (0xff>>i)): # First byte matches up
                        if not ((searchwords[i][len(word)-1] ^ data[searchindex+len(word)-1]) & (0xff<<(8-i))): # Last byte matches up
                            return (searchindex<<3) + i

            searchindex += 1

        return False

    def offset(data, offset):
        # Apply byte offset to data
        data = data[offset>>3:]
        if offset&0x07 == 0:
            return data

        # Apply bit offset to data
        for i in range(len(data)):
            data[i] = (data[i]<<(offset&0x07))&0xff
            if i+1 < len(data):
                data[i] = data[i] | (data[i+1]>>(8-(offset&0x07)))

        return data

class LUT:

    TABLE_SIZE = 256

    table = [
        0x00, 0x80, 0x40, 0xC0, 0x20, 0xA0, 0x60, 0xE0,
        0x10, 0x90, 0x50, 0xD0, 0x30, 0xB0, 0x70, 0xF0,
        0x08, 0x88, 0x48, 0xC8, 0x28, 0xA8, 0x68, 0xE8,
        0x18, 0x98, 0x58, 0xD8, 0x38, 0xB8, 0x78, 0xF8,
        0x04, 0x84, 0x44, 0xC4, 0x24, 0xA4, 0x64, 0xE4,
        0x14, 0x94, 0x54, 0xD4, 0x34, 0xB4, 0x74, 0xF4,
        0x0C, 0x8C, 0x4C, 0xCC, 0x2C, 0xAC, 0x6C, 0xEC,
        0x1C, 0x9C, 0x5C, 0xDC, 0x3C, 0xBC, 0x7C, 0xFC,
        0x02, 0x82, 0x42, 0xC2, 0x22, 0xA2, 0x62, 0xE2,
        0x12, 0x92, 0x52, 0xD2, 0x32, 0xB2, 0x72, 0xF2,
        0x0A, 0x8A, 0x4A, 0xCA, 0x2A, 0xAA, 0x6A, 0xEA,
        0x1A, 0x9A, 0x5A, 0xDA, 0x3A, 0xBA, 0x7A, 0xFA,
        0x06, 0x86, 0x46, 0xC6, 0x26, 0xA6, 0x66, 0xE6,
        0x16, 0x96, 0x56, 0xD6, 0x36, 0xB6, 0x76, 0xF6,
        0x0E, 0x8E, 0x4E, 0xCE, 0x2E, 0xAE, 0x6E, 0xEE,
        0x1E, 0x9E, 0x5E, 0xDE, 0x3E, 0xBE, 0x7E, 0xFE,
        0x01, 0x81, 0x41, 0xC1, 0x21, 0xA1, 0x61, 0xE1,
        0x11, 0x91, 0x51, 0xD1, 0x31, 0xB1, 0x71, 0xF1,
        0x09, 0x89, 0x49, 0xC9, 0x29, 0xA9, 0x69, 0xE9,
        0x19, 0x99, 0x59, 0xD9, 0x39, 0xB9, 0x79, 0xF9,
        0x05, 0x85, 0x45, 0xC5, 0x25, 0xA5, 0x65, 0xE5,
        0x15, 0x95, 0x55, 0xD5, 0x35, 0xB5, 0x75, 0xF5,
        0x0D, 0x8D, 0x4D, 0xCD, 0x2D, 0xAD, 0x6D, 0xED,
        0x1D, 0x9D, 0x5D, 0xDD, 0x3D, 0xBD, 0x7D, 0xFD,
        0x03, 0x83, 0x43, 0xC3, 0x23, 0xA3, 0x63, 0xE3,
        0x13, 0x93, 0x53, 0xD3, 0x33, 0xB3, 0x73, 0xF3,
        0x0B, 0x8B, 0x4B, 0xCB, 0x2B, 0xAB, 0x6B, 0xEB,
        0x1B, 0x9B, 0x5B, 0xDB, 0x3B, 0xBB, 0x7B, 0xFB,
        0x07, 0x87, 0x47, 0xC7, 0x27, 0xA7, 0x67, 0xE7,
        0x17, 0x97, 0x57, 0xD7, 0x37, 0xB7, 0x77, 0xF7,
        0x0F, 0x8F, 0x4F, 0xCF, 0x2F, 0xAF, 0x6F, 0xEF,
        0x1F, 0x9F, 0x5F, 0xDF, 0x3F, 0xBF, 0x7F, 0xFF
    ]

    def invert(data):
        if type(data) is list:
            for i in range(len(data)):
                data[i] = LUT.invert(data[i])
        else:
            data = LUT.table[data%LUT.TABLE_SIZE]
        return data

class CRC16:
    def __init__(self, value=0):
        self.set(value)

    def set(self, value):
        self.high = (value >> 8) & 0xff
        self.low = value & 0xff

    def get(self):
        return ((self.high & 0xff) << 8) | (self.low & 0xff)

    def print(self, invert=False):
        if not invert:
            print("0x{:02x}{:02x}".format(self.high, self.low))
        else:
            print("0x{:02x}{:02x}".format(LUT.invert(self.high), LUT.invert(self.low)))

class CRC:

    BITS = 4
    POLYNOME = 0x8005
    INITVALUE = 0x0000
    INVERT = True # NOTE: Should this be a variable or added into the mode?

    def check(data, verbose=0):
        if verbose>1:
            print("CRC Input Data:")
            Utilities.printhex(data)

        crc, table = CRC.calculate(CRC.POLYNOME, CRC.INITVALUE)
        if verbose>1:
            print("CRC Table:")
            Utilities.printhex(table)
            print("Initial CRC: ", end="")
            crc.print(True)

        for i in range(len(data)):
            value = data[i]
            if CRC.INVERT:
                value = LUT.invert(value)
            crc = CRC.update(crc, value, table, verbose)

        if verbose>0:
            if verbose>1:
                print("CRC Check Complete")
                print("Final CRC: ", end="")
                crc.print(True)
            if crc.get()>0:
                print("CRC Check Failed")
            else:
                print("CRC Check Successful!")

        return crc.get() # >0 = bad crc

    def calculate(polynome, initvalue, verbose=0):
        count = 1<<CRC.BITS
        table = [0 for i in range(count*2)]
        for i in range(0, count):
            value = CRC.generate(i, polynome, verbose)
            table[i+count] = (value >> 8) & 0xff
            table[i] = value & 0xff
        return CRC16(initvalue), table

    def generate(index, polynome, verbose=0):
        # Prepare initial register so that index is at MSB
        value = index
        value = (value << (16 - CRC.BITS)) & 0xffff

        for i in range(CRC.BITS):
            if value & 0x8000:
                value = ((value << 1) ^ polynome) & 0xffff
            else:
                value = (value << 1) & 0xffff

        return value

    def update(crc, value, table, verbose=0):
        crc = CRC.update_nibble(crc, (value>>4) & 0x0f, table, verbose)
        crc = CRC.update_nibble(crc, value & 0x0f, table, verbose)
        return crc

    def update_nibble(crc, value, table, verbose=0):
        # Step one, extract the Most significant 4 bits of the CRC register
        t = (crc.high>>4) & 0x0f

        # XOR in the data into the extracted bits
        t = t ^ (value & 0x0f)

        # Shift the CRC register left 4 bits
        crc.high = ((crc.high<<4)&0xf0) | ((crc.low>>4)&0x0f)
        crc.low = (crc.low<<4)&0xf0

        # Do the table lookups and XOR the result into the CRC tables
        crc.high = crc.high ^ table[t+16]
        crc.low = crc.low ^ table[t]

        return crc

class QD:

    BIT_MS = 0.004916

    INIT_MS = 500
    WINDOW_MS = 5500
    TOTAL_MS = 8000

    INIT_SIZE = False
    WINDOW_SIZE = False
    TOTAL_SIZE = False

    BLOCK_SIZE = 512
    BLOCKS = False

    HEADER = "DCDQDS10"

    def mstobytes(ms):
        return int(ms / QD.BIT_MS / 8)
    def stobytes(s):
        return QD.mstobytes(s * 1000.0)

    def calculate(verbose=0):
        if not QD.INIT_SIZE:
            QD.INIT_SIZE = QD.mstobytes(QD.INIT_MS)
        if not QD.WINDOW_SIZE:
            QD.WINDOW_SIZE = QD.mstobytes(QD.WINDOW_MS)
        if not QD.TOTAL_SIZE:
            QD.TOTAL_SIZE = QD.mstobytes(QD.TOTAL_MS)
        if not QD.BLOCKS:
            QD.BLOCKS = ((QD.TOTAL_SIZE + QD.BLOCK_SIZE-1) // QD.BLOCK_SIZE) + 2 # // = divide and remove decimal (same as Math.floor); extra 2 is for file header and track

        if verbose:
            print("Lead-In: {} sec -> {} bytes".format(QD.INIT_MS / 1000.0, QD.INIT_SIZE))
            print("Window:  {} sec -> {} bytes".format(QD.WINDOW_MS / 1000.0, QD.WINDOW_SIZE))
            print("Total:   {} sec -> {} bytes".format(QD.TOTAL_MS / 1000.0, QD.TOTAL_SIZE))
            print("Blocks:  {} x {} bytes = {} bytes".format(QD.BLOCKS, QD.BLOCK_SIZE, QD.BLOCKS * QD.BLOCK_SIZE))

    def generate(verbose=0):
        QD.calculate(verbose)
        data = [0 for i in range(QD.BLOCKS * QD.BLOCK_SIZE)]

        # Header
        for i in range(0, len(QD.HEADER)):
            data[i] = ord(QD.HEADER[i])
        for i in range(len(QD.HEADER), QD.BLOCK_SIZE):
            data[i] = 0x00

        # Track
        #  Format: "4I" = 4*unsigned int (4) = 16 bytes; "<" = little-endian;
        track = struct.pack("<4I", 1024, QD.TOTAL_SIZE, QD.INIT_SIZE, QD.INIT_SIZE + QD.WINDOW_SIZE)
        j = 0
        for i in range(QD.BLOCK_SIZE, QD.BLOCK_SIZE+len(track)):
            data[i] = track[j]
            j += 1

        for i in range(QD.BLOCK_SIZE+len(track), QD.BLOCK_SIZE*2):
            data[i] = 0x00

        # Data
        for i in range(QD.BLOCK_SIZE*2, QD.BLOCKS * QD.BLOCK_SIZE):
            data[i] = 0x11

        return data

    def writeraw(data, verbose=0, qd=False, offset=0, bit_offset=0):
        if not qd:
            qd = QD.generate(verbose)

        bit_offset = bit_offset&0x07

        j = QD.BLOCK_SIZE*2 + QD.INIT_SIZE + offset
        if bit_offset == 0:
            for i in range(min(len(data), QD.WINDOW_SIZE-offset)):
                qd[j+i] = ord(data[i])
        else:
            for i in range(min(len(data), QD.WINDOW_SIZE-offset-1)):
                for k in range(8):
                    Utilities.setbit(qd, (j<<3) + i + bit_offset + k, Utilities.getbit(data, (i<<3) + k))

        return qd

# Command Line

parser = argparse.ArgumentParser(description="MFM Encoder/Decoder")
parser.add_argument('--verbose', '-v', type=int)
parser.add_argument('--input', '-i', type=argparse.FileType('rb'))
parser.add_argument('--output', '-o', type=argparse.FileType('wb', 0))
parser.add_argument('--hex', '-s', type=str)
parser.add_argument('--mode', '-m', type=str, choices=['encode', 'decode', 'mfm-decode', 'mfm-encode', 'mfm-sync', 'lut-invert', 'qd-generate', 'crc-check'], required=True, nargs="+", help="multiple processes can be combined and processed in order")
parser.add_argument('--block', '-b', type=int, default=1)
parser.set_defaults(verbose=0, hex='', type='encode')

args = parser.parse_args()

if (type(args.mode) is str and args.mode == "encode") or (type(args.mode) is list and args.mode[0] == "encode"):
    args.mode = ["lut-invert", "mfm-encode", "lut-invert"]
elif (type(args.mode) is str and args.mode == "decode") or (type(args.mode) is list and args.mode[0] == "decode"):
    args.mode = ["lut-invert", "mfm-sync", "mfm-decode", "lut-invert"]

if args.hex != "":

    # Process hex string

    input = list(bytearray.fromhex(args.hex))
    output = Utilities.process(input, args.mode, args.verbose, args)
    Utilities.printhex(output)

elif args.input:

    # Process file and export

    dirname = path.dirname(args.input.name)
    filename = path.splitext(path.basename(args.input.name))[0]

    if not args.output:
        args.output = open("{}{}.{}".format(dirname, filename, Utilities.getext(args.mode)), "wb")

    # Read input into list of numbers
    input = []
    byte = False
    while True:
        byte = args.input.read(1)
        if not byte:
            break
        input.append(ord(byte))
    args.input.close()

    # Process data
    output = Utilities.process(input, args.mode, args.verbose, args)

    # Write output to file
    args.output.write(bytearray(output))
    args.output.close()

elif args.mode == "qd-generate" or (type(args.mode) is list and args.mode[0] == "qd-generate"):

    if not args.output:
        args.output = open("{}.{}".format("blank", Utilities.getext(args.mode)), "wb")

    # Get generated data
    output = Utilities.process(False, args.mode, args.verbose, args)

    # Write data to file
    args.output.write(bytearray(output))
    args.output.close()

else:
    print("Invalid parameters")
