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
    import string
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
            elif mode[i] == "syx-read":
                data = Sysex.read(data, verbose) # class Sample
            elif mode[i] == "qd-sample-blocks" and isinstance(data, Sample):
                data = QD.buildSampleBankBlocks(data, verbose)

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
        elif mode == "qd-generate" or mode == "qd-write":
            return "qd"

        return False

    def getbit(data, bit_offset):
        return (input[bit_offset>>3] >> (0x07-(bit_offset&0x07))) & 0x01

    def setbit(data, bit_offset, state):
        if state:
            data[bit_offset>>3] = data[bit_offset>>3] | (0x80 >> (bit_offset&0x07))
        else:
            data[bit_offset>>3] = data[bit_offset>>3] & ~(0x80 >> (bit_offset&0x07))

    def isalpha(c):
        chars = string.ascii_lowercase + string.ascii_uppercase
        return c in chars

    def isdigit(c):
        return c in string.digits

    def isfilesafe(c):
        if type(c) is int:
            c = chr(c)
        chars = string.ascii_lowercase + string.ascii_uppercase + string.digits + '.!()+-_'
        return c in chars

class MFM:

    BUFFER_SIZE = 10*1024

    mfmsyncword = [
        0x94, 0x4A, 0x94, 0x4A, 0x94, 0x4A, 0x94, 0x4A,
        0x94, 0x4A, 0x94, 0x4A, 0x94, 0x4A, 0x44, 0x91
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

    def get(self, invert=False):
        if not invert:
            return ((self.high & 0xff) << 8) | (self.low & 0xff)
        else:
            return (LUT.invert(self.high & 0xff) << 8) | LUT.invert(self.low & 0xff)

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

        return crc.get(True) # >0 = bad crc

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

    SYNCPRE = [0x16, 0x16, 0x16, 0x16, 0x16, 0x16, 0x16] #, 0xa5]
    SYNC = [0xa5]
    SYNCPOST = [0x16, 0x16, 0x16, 0x16, 0x16, 0x16, 0x16]

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

    def buildSampleBankBlocks(sample, verbose=0):
        banks = []

        for i in range(sample.SamplingStructure.offset, sample.SamplingStructure.offset + sample.SamplingStructure.length * sample.SamplingStructure.loops):
            blocks = []

            blocks.append(QD.buildFormatBlock())
            if verbose>2:
                print("Bank {} - Block {}:".format(i+1, 1))
                Utilities.printhex(blocks[0])

            blocks.append(QD.buildParamBlock(sample, i))
            if verbose>2:
                print("Bank {} - Block {}:".format(i+1, 2))
                Utilities.printhex(blocks[1])

            blocks.append(QD.buildWaveBlock(sample, i))
            if verbose>2:
                print("Bank {} - Block {}:".format(i+1, 3))
                Utilities.printhex(blocks[2])

            banks.append(blocks)

            break # for testing

        # Export bank blocks as binary files
        if verbose>1:
            print("Writing binary files for each bank block.")
            for i in range(len(banks)):
                for j in range(len(banks[i])):
                    filename = "bank-{}_block-{}.{}".format(i+1, j+1, "bin")
                    print("Writing {}.".format(filename))
                    file = open(filename, "wb")
                    file.write(bytearray(banks[i][j]))
                    file.close()


        return banks

    FORMAT_BLOCK_WORD = [0x02] # 0x02=?
    def buildFormatBlock():
        return QD.prepareBlock(QD.FORMAT_BLOCK_WORD)

    PARAM_BLOCK_SIZE = 0x46-3 # -3 = 1 for sync and 2 for crc
    TONE_NAME_OFFSET = 0x04
    ID_OFFSET = 0x1d
    ID_LENGTH = 10
    ID_WORD = "Roland S10" # no carriage return
    def buildParamBlock(sample, bank):
        data = [0 for i in range(QD.PARAM_BLOCK_SIZE)]

        data[1] = 0x40 # ?

        data[3] = 0x01 # ?

        # Tone Name
        for i in range(QD.TONE_NAME_OFFSET, QD.TONE_NAME_OFFSET+Sample.TONE_NAME_LENGTH):
            if i-QD.TONE_NAME_OFFSET < len(sample.ToneName):
                data[i] = ord(sample.ToneName[i-QD.TONE_NAME_OFFSET])
            else:
                data[i] = ord(" ")
        data[QD.TONE_NAME_OFFSET+Sample.TONE_NAME_LENGTH] = 0x0d # carriage return

        # 7 spaces?
        for i in range(QD.TONE_NAME_OFFSET+Sample.TONE_NAME_LENGTH+1, QD.TONE_NAME_OFFSET+Sample.TONE_NAME_LENGTH+1+7):
            data[i] = ord(" ")

        data[0x17] = 0xa0 # ?
        data[0x18] = 0xc0 # ?

        # ID
        for i in range(QD.ID_OFFSET, QD.ID_OFFSET+QD.ID_LENGTH):
            data[i] = ord(QD.ID_WORD[i-QD.ID_OFFSET])

        return QD.prepareBlock(data)

    WAVE_BLOCK_SIZE = 0xC0A6-3 # -3 = 1 for sync and 2 for crc
    WAVE_OFFSET = 0xef-8 # -8 is sync
    WAVE_DATA_SIZE = 32722 # 0x7FD2
    def buildWaveBlock(sample, bank):
        data = [0 for i in range(QD.WAVE_BLOCK_SIZE)]

        # TODO: Insert Wave Bank Parameters...

        startAddress = Sample.S10_MEMORY_BANK_SIZE * bank

        # Squeeze 2x12-bit into 3x8-bit
        for i in range(int(QD.WAVE_DATA_SIZE/2)):
            blockAddress = QD.WAVE_OFFSET + i*3
            memoryAddress = startAddress + i*2

            val1 = ((sample.Memory[memoryAddress+1]&0x0f)<<8) + (sample.Memory[memoryAddress+0]&0xff)
            val2 = ((sample.Memory[memoryAddress+3]&0x0f)<<8) + (sample.Memory[memoryAddress+2]&0xff)

            data[blockAddress+0] = (val1>>4) & 0xff
            data[blockAddress+2] = val1 & 0x0f # or +3??
            data[blockAddress+1] = (val2>>4) & 0xff
            data[blockAddress+2] = data[blockAddress+2] | ((val2&0x0f) << 4) # or +3??

        return QD.prepareBlock(data)

    def prepareBlock(data):
        data = QD.SYNC + data
        crc_word = CRC.check(data)
        data = data + [(crc_word>>8)&0xff, crc_word&0xff]
        data = QD.SYNCPRE + data + QD.SYNCPOST
        return data

class SamplingStructure:
    def __init__(self, index=0, name="A", offset=0, length=1, loops=1):
        self.index = index
        self.name = name
        self.offset = offset
        self.length = length
        self.loops = loops

class SampleBank:

    SAMPLE_RATE_30K = 30000
    SAMPLE_RATE_15K = 15000
    DEFAULT_SAMPLE_RATE = 30000 # SAMPLE_RATE_30K

    def __init__(self):
        self.LoopMode = 0
        self.ScanMode = 0
        self.RecKey = 0
        self.StartAddress = 0
        self.ManualLoopLength = 0
        self.ManualEndAddress = 0
        self.AutoLoopLength = 0
        self.AutoEndAddress = 0
        self.SampleRate = self.DEFAULT_SAMPLE_RATE

class Sample:

    S10_MEMORY_MAX = 256*1024 # 0x040000
    S10_MEMORY_BANK_SIZE = 0x010000
    SAMPLE_BANKS = 4
    TONE_NAME_LENGTH = 9

    def __init__(self):
        self.SamplingStructure = SamplingStructure()
        self.ToneName = " " * self.TONE_NAME_LENGTH
        self.Banks = [SampleBank for i in range(self.SAMPLE_BANKS)]
        self.Memory = [0 for i in range(self.S10_MEMORY_MAX)]
        # TODO: Dynamically set Banks with def setSamplingStructure? class SampleBank would have self.Sample for "A", etc

    def setToneNameChr(self, i, c):
        if i>len(self.ToneName):
            return False
        if type(c) is int:
            c = chr(c)
        self.ToneName = self.ToneName[:i] + c + self.ToneName[(i+1):]
        return True

class Sysex:

    SamplingStructures = [
        SamplingStructure(0, "A", 0, 1, 1),
        SamplingStructure(1, "B", 1, 1, 1),
        SamplingStructure(2, "C", 2, 1, 1),
        SamplingStructure(3, "D", 3, 1, 1),
        SamplingStructure(4, "AB", 0, 2, 1),
        SamplingStructure(5, "CD", 2, 2, 1),
        SamplingStructure(6, "ABCD", 0, 4, 1),
        SamplingStructure(7, "A-B", 0, 1, 2),
        SamplingStructure(8, "C-D", 2, 1, 2),
        SamplingStructure(9, "AB-CD", 0, 2, 2),
        SamplingStructure(10, "A-B-C-D", 0, 1, 4)
    ]

    def read(data, verbose=0):

        sample = Sample()

        sampleToggle = 0
        samplePosition = 0
        sampleData = 0

        syxByte = 0
        syxCounter = 0
        address = 0
        syxActive = False

        syxCommand = 0
        syxParam = 0

        wpOffs = 0 # Wave Parameter Offset
        wpBlock = 0 # Wave Parameter Block

        for x in range(len(data)):
            syxByte = data[x]

            # Sysex Start
            if syxByte == 0xf0:
                if verbose>1:
                    print("\nSystem Exclusive start.")
                syxCounter = 0
                syxActive = True
                continue

            # Sysex Stop
            if syxByte == 0xf7:
                if verbose>1:
                    print("System Exclusive stop. SysexCounter (minus header and stop) at: {}".format(syxCounter-8))
                syxActive = False
                continue

            if syxActive:

                # Manufacturer ID
                if syxCounter == 0:
                    if syxByte != 0x41:
                        if verbose>1:
                            print("Wrong manufacturer ID: 0x{:02x}.".format(syxByte))
                        syxActive = False
                    else:
                        if verbose>1:
                            print("Roland ID found.")
                    syxCounter += 1
                    continue

                # MIDI Channel
                if syxCounter == 1:
                    if syxByte > 0x0f:
                        if verbose>1:
                            print("Wrong MIDI basic channel.")
                        else:
                            print("MIDI basic channel: {}", syxByte+1)
                    syxCounter += 1
                    continue

                # Model ID
                if syxCounter == 2:
                    if syxByte != 0x10:
                        if verbose>1:
                            print("Wrong Model-ID.")
                        syxActive = False
                    else:
                        if verbose>1:
                            print("S-10 found.")
                    syxCounter += 1
                    continue

                # Command ID
                if syxCounter == 3:
                    syxCommand = syxByte
                    if verbose>1:
                        if syxCommand == 0x11: # RQ1
                            print("Command-ID: Request (one way).")
                        elif syxCommand == 0x12: # DT1
                            print("Command-ID: Data set (One way).")
                        elif syxCommand == 0x40: # WSD
                            print("Command-ID: Want to send data.")
                        elif syxCommand == 0x41: # RQD
                            print("Command-ID: Request data.")
                        elif syxCommand == 0x42: # DAT
                            print("Command-ID: Data set.")
                        elif syxCommand == 0x43: # ACK
                            print("Command-ID: Acknowledge.")
                        elif syxCommand == 0x45: # EOD
                            print("Command-ID: End of data.")
                        elif syxCommand == 0x4e: # ERR
                            print("Command-ID: Communication error.")
                        elif syxCommand == 0x4f: # RJC
                            print("Command-ID: Rejection.")
                    syxCounter += 1
                    continue

                # Address (only DT1)
                if syxCounter == 4 and syxCommand == 0x12:
                    if verbose>1:
                        print("Address: 0x{:02x}{:02x}{:02x}".format(data[x], data[x+1], data[x+2]))

                    address = ((data[x]&0xff)<<16) + ((data[x+1]&0xff)<<8) + (data[x+2]&0xff)
                    syxParam = 0
                    sampleToggle = 0
                    wpOffs = 0x00 # reset Wave Parameter Offset

                    # Wave Parameter
                    if address >= 0x00010000 and address <= 0x00010048:
                        syxParam = 1
                        wpBlock = 0
                        if verbose>0:
                            print("Wave parameter of block-1.")
                    if address >= 0x00010049 and address <= 0x00010111:
                        syxParam = 1
                        wpBlock = 1
                        if verbose>0:
                            print("Wave parameter of block-2.")
                    if address >= 0x00010112 and address <= 0x0001015a:
                        syxParam = 1
                        wpBlock = 2
                        if verbose>0:
                            print("Wave parameter of block-3.")
                    if address >= 0x0001015b and address <= 0x00010224:
                        syxParam = 1
                        wpBlock = 3
                        if verbose>0:
                            print("Wave parameter of block-4.")
                    if data[x] == 0x01 and data[x+1] == 0x08:
                        syxParam = 2
                        if verbose>0:
                            print("Performance parameter.")
                        # TODO: Implement performance parameters?

                    # Wave Data
                    if data[x] >= 0x02 and data[x] <= 0x11:
                        syxParam = 3
                        if verbose>1:
                            print("Previous SamplePosition set as 0x{:02x}".format(samplePosition))
                        samplePosition = ((data[x] - 0x02) << 14) + (data[x+1] << 7) + data[x+2]
                        if verbose>1:
                            print("SamplePosition set as 0x{:02x}".format(samplePosition))

                    if data[x] >= 0x02 and data[x] <= 0x05:
                        if verbose>1:
                            print("Wave data of bank-1.")
                    if data[x] >= 0x06 and data[x] <= 0x09:
                        if verbose>1:
                            print("Wave data of bank-2.")
                    if data[x] >= 0x0a and data[x] <= 0x0d:
                        if verbose>1:
                            print("Wave data of bank-3.")
                    if data[x] >= 0x0e and data[x] <= 0x11:
                        if verbose>1:
                            print("Wave data of bank-4.")

                if syxCounter >= 7:

                    # Wave Parameter
                    if syxParam == 1:
                        if syxCounter == 7+0x49: # When a second wave parameter block is in the same sysex chunk
                            if data[x+1] == 0xf7: # if next symbol is system exclusive stop, this is a stray symbol
                                if verbose>0:
                                    print("Stray symbol (next is system exclusive stop). Ignoring.")
                                syxActive = False
                                continue
                            wpOffs = 0x49

                            if verbose>1:
                                print("WPOffs is: {}".format(wpOffs))

                        # Destination Bank
                        if syxCounter == 7+wpOffs:
                            wpBlock = data[x+0x0a] # Destination bank (we set this early / first as we rely on it instead of memory address)
                            if verbose>0:
                                print("Destination bank: {}".format(wpBlock+1))
                            if wpBlock > Sample.SAMPLE_BANKS:
                                if verbose>0:
                                    print("WPBlock error. Ignoring.")
                                syxActive = False
                                continue

                        # Tone Name
                        if syxCounter >= 7+wpOffs and syxCounter <= 7+wpOffs+0x08:
                            # We don't care about wpBlock, all banks should have the ToneNames should be the same
                            if Utilities.isfilesafe(data[x]):
                                sample.setToneNameChr(syxCounter-7-wpOffs, data[x])
                            else:
                                sample.setToneNameChr(syxCounter-7-wpOffs, " ")
                            if syxCounter == 7+wpOffs+8:
                                sample.ToneName = sample.ToneName.strip()
                                if verbose>0:
                                    print("Tone Name: '{}'".format(sample.ToneName))

                        # Sampling Structure
                        if syxCounter == 7+wpOffs+0x09 and data[x] < len(Sysex.SamplingStructures):
                            sample.SamplingStructure = Sysex.SamplingStructures[data[x]] # Multiple bank sampling structures will overwrite

                            if verbose:
                                print("Sampling structure: {} - {}".format(sample.SamplingStructure.index, sample.SamplingStructure.name))

                        # syxCounter == 7+wpOffs+0x0a # Destination Bank

                        # Sampling Rate
                        if syxCounter == 7+wpOffs+0x0b:
                            if data[x] & 0x01:
                                sample.Banks[wpBlock].SampleRate = SampleBank.SAMPLE_RATE_30K
                                if verbose>0:
                                    print("Smapling rate: 15 kHz")
                            else:
                                if verbose>0:
                                    print("Sampling rate: 30 kHz")

                        # Loop Mode & Scan Mode
                        if syxCounter == 7+wpOffs+0x0c:
                            if (data[x] & 0x0c) == 0x00:
                                if verbose>0:
                                    print("Loop mode: 1 shot")
                            if (data[x] & 0x0c) == 0x04:
                                sample.Banks[wpBlock].LoopMode = 1
                                if verbose>0:
                                    print("Loop mode: Manual")
                            if (data[x] & 0x0c) == 0x08:
                                sample.Banks[wpBlock].LoopMode = 2
                                if verbose>0:
                                    print("Loop mode: Auto")

                            if (data[x] & 0x03) == 0x00:
                                if verbose>0:
                                    print("Scan mode: Forward")
                            if (data[x] & 0x03) == 0x01:
                                sample.Banks[wpBlock].ScanMode = 1
                                if verbose>0:
                                    print("Scan mode: Alternate")
                            if (data[x] & 0x03) == 0x02:
                                sample.Banks[wpBlock].ScanMode = 2
                                if verbose>0:
                                    print("Scan mode: Backward")

                        # Rec key number
                        if syxCounter == 7+wpOffs+0x0d:
                            sample.Banks[wpBlock].RecKey = (data[x] & 0x0f) + ((data[x+1] & 0x0f) << 4)
                            if verbose>0:
                                print("Rec key number: {}".format(sample.Banks[wpBlock].RecKey))

                        # Start address, Manual and auto loop length and end address
                        if syxCounter == 7+wpOffs+0x11:
                            # (StartAddress-65536) / 32768 seems to be the same as destination bank
                            sample.Banks[wpBlock].StartAddress = (
                                ((data[x] & 0x0f) << 8)
                                + ((data[x+1] & 0x0f) << 12)
                                + ((data[x+2] & 0x0f))
                                + ((data[x+3] & 0x0f) << 4)
                                + ((data[x+21] & 0x0c) << 14)
                            )
                            if sample.Banks[wpBlock].StartAddress > 65535:
                                sample.Banks[wpBlock].StartAddress -= 65536

                            sample.Banks[wpBlock].ManualLoopLength = (
                                ((data[x+4] & 0x0f) << 8) +
                                ((data[x+5] & 0x0f) << 12) +
                                ((data[x+6] & 0x0f)) +
                                ((data[x+7] & 0x0f) << 4) +
                                ((data[x+20] & 0x0c) << 14)
                            )
                            sample.Banks[wpBlock].ManualLoopLength -= 1

                            sample.Banks[wpBlock].ManualEndAddress = (
                                ((data[x+8] & 0x0f) << 8) +
                                ((data[x+9] & 0x0f) << 12) +
                                ((data[x+10] & 0x0f)) +
                                ((data[x+11] & 0x0f) << 4) +
                                ((data[x+20] & 0x03) << 16)
                            )
                            if sample.Banks[wpBlock].ManualEndAddress > 65535:
                                sample.Banks[wpBlock].ManualEndAddress -= 65536
                            sample.Banks[wpBlock].ManualEndAddress -= sample.Banks[wpBlock].StartAddress

                            sample.Banks[wpBlock].AutoLoopLength = (
    							((data[x+12] & 0x0f) << 8) +
    							((data[x+13] & 0x0f) << 12) +
    							((data[x+14] & 0x0f)) +
    							((data[x+15] & 0x0f) << 4) +
    							((data[x+23] & 0x0c) << 14)
                            )
                            sample.Banks[wpBlock].AutoLoopLength -= 1

                            sample.Banks[wpBlock].AutoEndAddress = (
                                ((data[x+16] & 0x0f) << 8) +
                                ((data[x+17] & 0x0f) << 12) +
                                ((data[x+18] & 0x0f)) +
                                ((data[x+19] & 0x0f) << 4) +
                                ((data[x+23] & 0x03) << 16)
                            )
                            if sample.Banks[wpBlock].AutoEndAddress > 65535:
                                sample.Banks[wpBlock].AutoEndAddress -= 65536
                            sample.Banks[wpBlock].AutoEndAddress -= sample.Banks[wpBlock].StartAddress

                            if verbose>0:
                                print("Start Address: {}".format(sample.Banks[wpBlock].StartAddress))
                                print("Manual Loop Length: {}".format(sample.Banks[wpBlock].ManualLoopLength))
                                print("Manual End Address (minus Start Address): {}".format(sample.Banks[wpBlock].ManualEndAddress))
                                print("Auto Loop Length: {}".format(sample.Banks[wpBlock].AutoLoopLength))
                                print("Auto End Address (minus Start Address): {}".format(sample.Banks[wpBlock].AutoEndAddress))

                    # Wave Data
                    if syxParam == 3:
                        if sampleToggle % 2 != 0:
                            # Make sure we never write outside S-10 memory
                            if samplePosition+1 > Sample.S10_MEMORY_MAX:
                                if verbose>0:
                                    print("SamplePosition outside S-10 memory boundary.")
                                    break

                            sampleData = ((data[x-1] & 0x7f) << 7) + (data[x] & 0x7c) # 12-bit
                            #sampleData = ((data[x-1] & 0x7f) << 9) + ((data[x] & 0x7c) << 2) # 16-bit
                            sample.Memory[samplePosition] = 0xff & sampleData
                            sample.Memory[samplePosition+1] = 0xff & (sampleData >> 8)

                            samplePosition += 2

                        sampleToggle += 1

                syxCounter += 1

        if verbose>0:
            print("Final SamplePosition: {}".format(samplePosition))

        return sample

class Wav:

    def processSample():
        # TODO: Convert sample to wave sound file
        pass

# Command Line

parser = argparse.ArgumentParser(description="MFM Encoder/Decoder")
parser.add_argument('--verbose', '-v', type=int)
parser.add_argument('--input', '-i', type=argparse.FileType('rb'))
parser.add_argument('--output', '-o', type=argparse.FileType('wb', 0))
parser.add_argument('--hex', '-s', type=str)
parser.add_argument('--mode', '-m', type=str, choices=['encode', 'decode', 'mfm-decode', 'mfm-encode', 'mfm-sync', 'lut-invert', 'qd-generate', 'crc-check', 'syx-read', 'syx-to-qd'], required=True, nargs="+", help="multiple processes can be combined and processed in order")
parser.add_argument('--block', '-b', type=int, default=1)
parser.set_defaults(verbose=0, hex='', type='encode')

args = parser.parse_args()

# Mode Combos

if (type(args.mode) is str and args.mode == "encode") or (type(args.mode) is list and args.mode[0] == "encode"):
    args.mode = ["lut-invert", "mfm-encode", "lut-invert"]
elif (type(args.mode) is str and args.mode == "decode") or (type(args.mode) is list and args.mode[0] == "decode"):
    args.mode = ["lut-invert", "mfm-sync", "mfm-decode", "lut-invert"]
elif (type(args.mode) is str and args.mode == "syx-to-qd") or (type(args.mode) is list and args.mode[0] == "syx-to-qd"):
    args.mode = ['syx-read', 'qd-sample-blocks']

if args.hex != "":

    # Process hex string

    input = list(bytearray.fromhex(args.hex))
    output = Utilities.process(input, args.mode, args.verbose, args)
    Utilities.printhex(output)

elif args.input:

    # Process file and export

    dirname = path.dirname(args.input.name)
    filename = path.splitext(path.basename(args.input.name))[0]

    if not args.output and Utilities.getext(args.mode) != False:
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

    if args.output:
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
