"""GIF decoder/encoder in pure Python.

Notes:
    GCT = Global Color Table
    LCT = Local Color Table
    LSD = Logical Screen Descriptor
    LZW = Lempel-Ziv-Welch"""

import argparse
import math
import os
import struct
import sys

class GIFError(Exception):
    """An exception for GIF-related errors."""

class RGBError(Exception):
    """An exception for errors related to raw RGB files."""

# --- Decoding ------------------------------------------------------------------------------------

def read_bytes(handle, length):
    """Read bytes from file."""

    data = handle.read(length)
    if len(data) < length:
        raise GIFError("EOF")
    return data

def skip_bytes(handle, length):
    """Skip bytes in file."""

    origPos = handle.tell()
    handle.seek(length, 1)
    if handle.tell() - origPos < length:
        raise GIFError("EOF")

def read_subblocks(handle):
    """Generate data from GIF subblocks."""

    SBSize = read_bytes(handle, 1)[0]
    while SBSize:
        chunk = read_bytes(handle, SBSize + 1)
        yield chunk[:-1]
        SBSize = chunk[-1]

def skip_subblocks(handle):
    """Skip GIF subblocks."""

    SBSize = read_bytes(handle, 1)[0]
    while SBSize:
        skip_bytes(handle, SBSize)
        SBSize = read_bytes(handle, 1)[0]

def read_image_info(handle):
    """Read information of one image in GIF file.
    Handle position must be at first byte after "," of Image Descriptor."""

    (width, height, packedFields) = struct.unpack("<4x2HB", read_bytes(handle, 9))
    if min(width, height) == 0:
        raise GIFError("IMAGE_AREA_ZERO")

    if packedFields >> 7:  # LCT?
        LCTAddr = handle.tell()
        LCTBits = (packedFields & 7) + 1
        skip_bytes(handle, 2 ** LCTBits * 3)
    else:
        LCTAddr = None
        LCTBits = None

    LZWPalBits = read_bytes(handle, 1)[0]
    if not 2 <= LZWPalBits <= 11:
        raise GIFError("INVALID_LZW_PALETTE_BIT_DEPTH")

    return {
        "width":      width,
        "height":     height,
        "interlace":  bool((packedFields >> 6) & 1),  # image data interlaced?
        "LCTAddr":    LCTAddr,        # LCT address or None
        "LCTBits":    LCTBits,        # LCT bit depth or None
        "LZWPalBits": LZWPalBits,     # palette bit depth in LZW encoding
        "LZWAddr":    handle.tell(),  # LZW data address
    }

def skip_extension_block(handle):
    """Skip Extension block in GIF file.
    Handle position must be at first byte after Extension Introducer ('!')."""

    label = read_bytes(handle, 1)[0]
    if label in (0x01, 0xf9, 0xff):
        # Plain Text Extension, Graphic Control Extension, Application Extension
        skip_bytes(handle, read_bytes(handle, 1)[0])
    elif label != 0xfe:
        # not Comment Extension
        raise GIFError("INVALID_EXTENSION_LABEL")
    skip_subblocks(handle)

def read_first_image_info(handle):
    """Return read_image_info() for first image in GIF file, or None.
    Ignore any extension blocks before the image.
    Handle position must be at first byte after GCT (or LSD, if there's no GCT)."""

    while True:
        blockType = read_bytes(handle, 1)
        if blockType == b",":  # Image Descriptor
            return read_image_info(handle)
        elif blockType == b"!":  # Extension
            skip_extension_block(handle)
        elif blockType == b";":  # Trailer
            return None
        else:
            raise GIFError("INVALID_BLOCK_TYPE")

def read_GIF(handle):
    """Read information of GIF file (first image only)."""

    handle.seek(0)

    # Header and LSD
    (id_, version, packedFields) = struct.unpack("<3s3s4xB2x", read_bytes(handle, 13))

    if id_ != b"GIF":
        raise GIFError("NOT_A_GIF_FILE")
    if version not in (b"87a", b"89a"):
        print("Warning: unknown GIF version.", file=sys.stderr)

    if packedFields >> 7:
        # has GCT
        palAddr = handle.tell()
        palBits = (packedFields & 7) + 1
        skip_bytes(handle, 2 ** palBits * 3)
    else:
        palAddr = None
        palBits = None

    imageInfo = read_first_image_info(handle)
    if imageInfo is None:
        raise GIFError("NO_IMAGES_IN_FILE")

    if imageInfo["LCTAddr"] is not None:
        # use LCT instead of GCT
        palAddr = imageInfo["LCTAddr"]
        palBits = imageInfo["LCTBits"]
    elif palAddr is None:
        raise GIFError("NO_PALETTE")

    return {
        "width":      imageInfo["width"],
        "height":     imageInfo["height"],
        "interlace":  imageInfo["interlace"],   # image data interlaced?
        "palAddr":    palAddr,                  # palette address
        "palBits":    palBits,                  # palette bit depth
        "LZWPalBits": imageInfo["LZWPalBits"],  # palette bit depth in LZW encoding
        "LZWAddr":    imageInfo["LZWAddr"],     # LZW data address
    }

def decode_LZW_data(LZWData, palBits, args):
    """Decode LZW data (bytes).
    palBits: palette bit depth in LZW encoding (2...8)
    args: from argparse
    generate: indexed image data as bytes (1 byte/pixel)"""

    # constants
    minCodeLen = palBits + 1    # initial length of LZW codes (3...9)
    maxCodeLen = 12             # maximum length of LZW codes
    clearCode  = 1 << palBits   # LZW clear code
    endCode    = clearCode + 1  # LZW end code
    minDictLen = clearCode + 2  # initial length of LZW dictionary

    # variables
    bytePos = 0            # byte position in LZW data
    bitPos  = 0            # bit  position in LZW data
    codeLen = minCodeLen   # length of LZW codes
    entry   = bytearray()  # entry to output
    # LZW dictionary; index: code, value: entry (reference to another code, final byte)
    LZWDict = [(-1, i) for i in range(minDictLen)]

    while True:
        if bitPos + codeLen > (len(LZWData) - bytePos) << 3:
            raise GIFError("EOF")

        # read code
        code = LZWData[bytePos]
        if codeLen > 8 - bitPos:
            code |= LZWData[bytePos+1] << 8
            if codeLen > 16 - bitPos:
                code |= LZWData[bytePos+2] << 16
        code >>= bitPos
        code &= (1 << codeLen) - 1
        if args.log:
            print(format(code, f"0{codeLen}b"))

        bitPos += codeLen
        bytePos += bitPos >> 3
        bitPos &= 7

        if code == clearCode:
            LZWDict = LZWDict[:minDictLen]
            codeLen = minCodeLen
            prevCode = None
        elif code == endCode:
            break
        else:
            # dictionary entry
            if prevCode is not None:
                # entry to take first byte from for new dictionary entry
                if code < len(LZWDict):
                    suffixCode = code
                elif code == len(LZWDict):
                    suffixCode = prevCode
                else:
                    raise GIFError("INVALID_LZW_CODE")
                # get first byte of entry
                while suffixCode != -1:
                    (suffixCode, suffixByte) = LZWDict[suffixCode]
                # add entry to dictionary
                LZWDict.append((prevCode, suffixByte))
                prevCode = None
            if code < len(LZWDict) < 1 << maxCodeLen:
                prevCode = code
            if len(LZWDict) == 1 << codeLen and codeLen < maxCodeLen:
                codeLen += 1
            # emit current entry
            entry.clear()
            while code != -1:
                (code, byte) = LZWDict[code]
                entry.append(byte)
            yield entry[::-1]

def deinterlace_image(imageData, width):
    """Deinterlace image data (bytes, 1 byte/pixel).
    generate: one pixel row per call"""

    # group 1: pixel rows 0,  8, 16, ...
    # group 2: pixel rows 4, 12, 20, ...
    # group 3: pixel rows 2,  6, 10, ...
    # group 4: pixel rows 1,  3,  5, ...

    height = len(imageData) // width

    group2Start = (height + 7) // 8  # pixel rows in group  1
    group3Start = (height + 3) // 4  # pixel rows in groups 1...2
    group4Start = (height + 1) // 2  # pixel rows in groups 1...3

    # sy = source pixel row, dy = destination pixel row
    for dy in range(height):
        if dy % 8 == 0:
            sy = dy // 8
        elif dy % 8 == 4:
            sy = group2Start + dy // 8
        elif dy % 4 == 2:
            sy = group3Start + dy // 4
        else:
            sy = group4Start + dy // 2
        yield imageData[sy*width:(sy+1)*width]

def decode_GIF(GIFHandle, rawHandle, args):
    """Decode or validate GIF.
    If decoding, write raw RGB data (RGBRGB...) to rawHandle."""

    info = read_GIF(GIFHandle)

    GIFHandle.seek(info["palAddr"])
    palette = read_bytes(GIFHandle, 2 ** info["palBits"] * 3)

    GIFHandle.seek(info["LZWAddr"])
    imageData = b"".join(read_subblocks(GIFHandle))

    # decode image data
    imageData = b"".join(decode_LZW_data(imageData, info["LZWPalBits"], args))
    if info["palBits"] < 8 and max(imageData) >= 2 ** info["palBits"]:
        raise GIFError("INVALID_INDEX_IN_IMAGE_DATA")

    if info["interlace"]:
        # deinterlace
        imageData = b"".join(deinterlace_image(imageData, info["width"]))

    # convert palette into a tuple of 3-byte colors
    palette = tuple(palette[pos:pos+3] for pos in range(0, len(palette), 3))

    if args.operation == "d":
        # write raw RGB data
        rawHandle.seek(0)
        for i in imageData:
            rawHandle.write(palette[i])

# --- Encoding ------------------------------------------------------------------------------------

def read_raw_image(handle):
    """Generate one pixel (bytes: RGB) per call from raw RGB image (bytes: RGBRGB...)."""

    pixelCount = handle.seek(0, 2) // 3
    handle.seek(0)
    for pos in range(pixelCount):
        yield handle.read(3)

def get_palette_from_raw_image(handle):
    """Create palette (bytes: RGBRGB...) from raw RGB image (bytes: RGBRGB...)."""

    palette = set()
    for color in read_raw_image(handle):
        palette.add(color)
        if len(palette) > 256:
            raise RGBError("TOO_MANY_COLORS")
    return b"".join(sorted(palette))

def raw_image_to_indexed(handle, palette):
    """Convert raw RGB image (bytes: RGBRGB...) into indexed image (1 byte/pixel)
    using palette (bytes: RGBRGB...). Generate 1 pixel per call."""

    RGBToIndex = dict((palette[i*3:(i+1)*3], i) for i in range(len(palette) // 3))
    for color in read_raw_image(handle):
        yield RGBToIndex[color]

def get_palette_bit_depth(colorCount):
    """How many bits needed for palette."""

    return max(math.ceil(math.log2(colorCount)), 1)

def encode_LZW_data(palette, imageData, args):
    """Encode image data (1 byte/pixel) using LZW and palette (bytes: RGBRGB...).
    args: from argparse. Generate bytes."""

    # note: encodes wolf3.gif and wolf4.gif in a different way than GIMP

    # constants
    palBits    = max(get_palette_bit_depth(len(palette) // 3), 2)  # palette bit depth in encoding
    minCodeLen = palBits + 1   # minimum length of LZW codes
    maxCodeLen = 12            # maximum length of LZW codes
    palSize    = 1 << palBits  # length of palette
    clearCode  = palSize       # LZW clear code
    endCode    = palSize + 1   # LZW end code

    # variables
    inputPos  = 0            # position in input
    codeLen   = minCodeLen   # length of LZW codes
    LZWByte   = 0            # next byte to output
    LZWBitPos = 0            # number of bits in LZWByte
    entry     = bytearray()  # LZW dictionary entry
    # LZW dictionary: {entry: code, ...}; note: doesn't contain clear and end codes,
    # so the actual length is len() + 2
    LZWDict = dict((bytes((i,)), i) for i in range(palSize))

    # output clear code
    LZWByte = clearCode
    LZWBitPos = codeLen
    while LZWBitPos >= 8:
        yield LZWByte & 0xff
        LZWByte >>= 8
        LZWBitPos -= 8
    if args.log:
        print(format(clearCode, f"0{codeLen}b"))

    while inputPos < len(imageData):
        # find longest entry that's a prefix of remaining image data, and corresponding code
        entry.clear()
        for pos in range(inputPos, len(imageData)):
            entry.append(imageData[pos])
            try:
                code = LZWDict[bytes(entry)]
            except KeyError:
                entry = entry[:-1]
                break
        inputPos += len(entry)

        # output code
        LZWByte |= code << LZWBitPos
        LZWBitPos += codeLen
        while LZWBitPos >= 8:
            yield LZWByte & 0xff
            LZWByte >>= 8
            LZWBitPos -= 8
        if args.log:
            print(format(code, f"0{codeLen}b"))

        if inputPos < len(imageData):
            if len(LZWDict) + 2 < (1 << maxCodeLen):
                # dictionary isn't full
                # add entry: current entry plus next pixel
                entry.append(imageData[inputPos])
                LZWDict[bytes(entry)] = len(LZWDict) + 2
                if len(LZWDict) + 2 == (1 << codeLen) + 1:
                    codeLen += 1
            else:
                # dictionary is full
                # output clear code
                LZWByte |= clearCode << LZWBitPos
                LZWBitPos += codeLen
                while LZWBitPos >= 8:
                    yield LZWByte & 0xff
                    LZWByte >>= 8
                    LZWBitPos -= 8
                if args.log:
                    print(format(clearCode, f"0{codeLen}b"))
                # initialize dictionary
                LZWDict = dict((bytes((i,)), i) for i in range(palSize))
                codeLen = minCodeLen

    # output end code
    LZWByte |= endCode << LZWBitPos
    LZWBitPos += codeLen
    while LZWBitPos > 0:
        yield LZWByte & 0xff
        LZWByte >>= 8
        LZWBitPos -= 8
    if args.log:
        print(format(endCode, f"0{codeLen}b"))

def write_GIF(width, height, palette, LZWData, handle):
    """Write a GIF file (version 87a, with GCT, one image).
    palette: bytes RGBRGB..., LZWData: bytes"""

    palBits = get_palette_bit_depth(len(palette) // 3)

    handle.seek(0)

    # Header and LSD
    packedFields = 0x80 | (palBits - 1)
    handle.write(struct.pack("<6s2H3B", b"GIF87a", width, height, packedFields, 0, 0))

    # GCT (padded)
    handle.write(palette + (2 ** palBits * 3 - len(palette)) * b"\x00")

    # Image Descriptor
    imgDesc = struct.pack("<s4HB", b",", 0, 0, width, height, 0)
    handle.write(imgDesc)

    # palette bit depth in LZW encoding
    handle.write(bytes((max(palBits, 2),)))

    # LZW data
    pos = 0
    while pos < len(LZWData):
        SBSize = min(255, len(LZWData) - pos)
        handle.write(bytes((SBSize,)) + LZWData[pos:pos+SBSize])
        pos += SBSize

    # empty subblock and Trailer
    handle.write(b"\x00;")

def encode_GIF(rawHandle, GIFHandle, args):
    """Convert raw RGB image (bytes: RGBRGB...) into GIF.
    args: from argparse"""

    (height, remainder) = divmod(rawHandle.seek(0, 2), args.width * 3)

    if remainder:
        raise RGBError("FILE_SIZE_NOT_DIVISIBLE_BY_WIDTH_TIMES_THREE")
    if height == 0:
        raise RGBError("FILE_EMPTY")
    if height > 65535:
        raise RGBError("IMAGE_TOO_TALL")

    palette = get_palette_from_raw_image(rawHandle)
    imageData = bytes(raw_image_to_indexed(rawHandle, palette))
    LZWData = bytes(encode_LZW_data(palette, imageData, args))
    write_GIF(args.width, height, palette, LZWData, GIFHandle)

# --- Common --------------------------------------------------------------------------------------

def parse_arguments():
    """Parse command line arguments using argparse."""

    parser = argparse.ArgumentParser(
        description="Decode/encode a GIF file into/from raw RGB data (bytes: RGBRGB...; "
        "order of pixels: first right, then down; file extension '.data' in GIMP)."
    )

    parser.add_argument(
        "-o", "--operation", choices=("d", "e"),
        help="What to do (d=decode, e=encode). Required."
    )
    parser.add_argument(
        "-w", "--width", type=int,
        help="Width of input file in pixels (encoding only)."
    )
    parser.add_argument(
        "-l", "--log", action="store_true",
        help="Print decode/encode log."
    )
    parser.add_argument(
        "input_file",
        help="File to read."
    )
    parser.add_argument(
        "output_file",
        help="File to write."
    )

    args = parser.parse_args()

    if args.operation is None:
        sys.exit("-o/--operation argument is required.")
    if args.operation == "e":
        if args.width is None:
            sys.exit("-w/--width is required when encoding.")
        elif not 1 <= args.width <= 65535:
            sys.exit("Invalid width.")

    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found.")
    if os.path.exists(args.output_file):
        sys.exit("Output file already exists.")

    return args

def main():
    args = parse_arguments()

    try:
        with open(args.input_file, "rb") as sourceHnd, open(args.output_file, "wb") as targetHnd:
            if args.operation == "d":
                decode_GIF(sourceHnd, targetHnd, args)
            else:
                encode_GIF(sourceHnd, targetHnd, args)
    except OSError:
        sys.exit("Error reading/writing files.")
    except GIFError as error:
        sys.exit(f"GIF error: {error}")
    except RGBError as error:
        sys.exit(f"Raw RGB data error: {error}")

if __name__ == "__main__":
    main()

