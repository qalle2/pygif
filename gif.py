"""GIF decoder/encoder in pure Python.

Notes:
    GCT = Global Color Table
    LCT = Local Color Table
    LSD = Logical Screen Descriptor
    LZW = Lempel-Ziv-Welch"""

import math
import os
import struct
import sys

HELP_TEXT = """\
Decodes a GIF file into raw RGB data or encodes raw RGB data into a GIF file.
(Bytes in raw RGB data: RGBRGB...; order of pixels: first right, then down;
file extension ".data" in GIMP.)

Arguments when decoding: SOURCE TARGET
    SOURCE = GIF file to read
    TARGET = raw RGB data file to write

Arguments when encoding: SOURCE WIDTH TARGET
    SOURCE = raw RGB data file to read
    WIDTH  = width of SOURCE in pixels
    TARGET = GIF file to write"""

# --- Decoding ------------------------------------------------------------------------------------

def read_bytes(handle, length):
    """Read bytes from file."""

    data = handle.read(length)
    if len(data) < length:
        raise Exception("EOF")
    return data

def skip_bytes(handle, length):
    """Skip bytes in file."""

    origPos = handle.tell()
    handle.seek(length, 1)
    if handle.tell() - origPos < length:
        raise Exception("EOF")

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
        raise Exception("IMAGE_AREA_ZERO")

    if packedFields >> 7:  # LCT?
        LCTAddr = handle.tell()
        LCTBits = (packedFields & 7) + 1
        skip_bytes(handle, 2 ** LCTBits * 3)
    else:
        LCTAddr = None
        LCTBits = None

    LZWPalBits = read_bytes(handle, 1)[0]
    if not 2 <= LZWPalBits <= 11:
        raise Exception("INVALID_LZW_PALETTE_BIT_DEPTH")

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
        raise Exception("INVALID_EXTENSION_LABEL")
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
            raise Exception("INVALID_BLOCK_TYPE")

def read_GIF(handle):
    """Read information of GIF file (first image only)."""

    handle.seek(0)

    # Header and LSD
    (id_, version, packedFields) = struct.unpack("<3s3s4xB2x", read_bytes(handle, 13))

    if id_ != b"GIF":
        raise Exception("NOT_A_GIF_FILE")
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
        raise Exception("NO_IMAGES_IN_FILE")

    if imageInfo["LCTAddr"] is not None:
        # use LCT instead of GCT
        palAddr = imageInfo["LCTAddr"]
        palBits = imageInfo["LCTBits"]
    elif palAddr is None:
        raise Exception("NO_PALETTE")

    return {
        "width":      imageInfo["width"],
        "height":     imageInfo["height"],
        "interlace":  imageInfo["interlace"],   # image data interlaced?
        "palAddr":    palAddr,                  # palette address
        "palBits":    palBits,                  # palette bit depth
        "LZWPalBits": imageInfo["LZWPalBits"],  # palette bit depth in LZW encoding
        "LZWAddr":    imageInfo["LZWAddr"],     # LZW data address
    }

def decode_LZW_data(LZWData, palBits):
    """Decode LZW data (bytes).
    palBits: palette bit depth in LZW encoding
    generate: indexed image data as bytes (1 byte/pixel)"""

    # constants
    clearCode = 1 << palBits      # LZW clear code
    endCode = clearCode + 1       # LZW end code
    initialCodeLen = palBits + 1  # initial length of LZW codes
    maxCodeLen = 12               # maximum length of LZW codes
    initialDictLen = endCode + 1  # initial length of LZW dictionary

    # variables
    bytePos = 0               # byte position in LZW data
    bitPos = 0                # bit  position in LZW data
    codeLen = initialCodeLen  # length of LZW codes
    entry = bytearray()       # entry to output
    # LZW dictionary; index: code, value: entry (reference to another code, final byte)
    LZWDict = [(-1, i) for i in range(initialDictLen)]

    while True:
        if bitPos + codeLen > (len(LZWData) - bytePos) << 3:
            raise Exception("EOF")

        # read code
        code = LZWData[bytePos]
        if codeLen > 8 - bitPos:
            code |= LZWData[bytePos+1] << 8
            if codeLen > 16 - bitPos:
                code |= LZWData[bytePos+2] << 16
        code >>= bitPos
        code &= (1 << codeLen) - 1

        bitPos += codeLen
        bytePos += bitPos >> 3
        bitPos &= 7

        if code == clearCode:
            LZWDict = LZWDict[:initialDictLen]
            codeLen = initialCodeLen
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
                    raise Exception("INVALID_LZW_CODE")
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

def GIF_to_raw_image(GIFHandle, rawHandle):
    """Convert GIF into raw RGB data (bytes: RGBRGB...)."""

    info = read_GIF(GIFHandle)

    GIFHandle.seek(info["palAddr"])
    palette = read_bytes(GIFHandle, 2 ** info["palBits"] * 3)

    GIFHandle.seek(info["LZWAddr"])
    imageData = b"".join(read_subblocks(GIFHandle))

    # decode image data
    imageData = b"".join(decode_LZW_data(imageData, info["LZWPalBits"]))
    if info["palBits"] < 8 and max(imageData) >= 2 ** info["palBits"]:
        raise Exception("INVALID_INDEX_IN_IMAGE_DATA")

    if info["interlace"]:
        # deinterlace
        imageData = b"".join(deinterlace_image(imageData, info["width"]))

    # convert palette into a tuple of 3-byte colors
    palette = tuple(palette[pos:pos+3] for pos in range(0, len(palette), 3))

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
            raise Exception("TOO_MANY_COLORS")
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

def encode_LZW_data(palette, imageData):
    """Encode image data (1 byte/pixel) using LZW and palette (bytes: RGBRGB...).
    Generate bytes."""

    # note: encodes wolf3.gif and wolf4.gif in a different way than GIMP

    # constants
    palBits = max(get_palette_bit_depth(len(palette) // 3), 2)  # palette bit depth in encoding
    minCodeLen = palBits + 1  # minimum length of LZW codes
    maxCodeLen = 12           # maximum length of LZW codes
    clearCode = 1 << palBits  # LZW clear code
    endCode = clearCode + 1   # LZW end code
    palSize = clearCode       # length of palette

    # variables
    inputPos = 0          # position in input
    codeLen = minCodeLen  # length of LZW codes
    LZWByte = 0           # next byte to output
    LZWBitPos = 0         # number of bits in LZWByte
    # LZW dictionary: {entry: code, ...}; note: doesn't contain clear and end codes,
    # so the actual length is len() + 2
    LZWDict = dict((bytes((i,)), i) for i in range(palSize))
    entry = bytearray()  # prefix of remaining image data to search for in dictionary

    # output clear code
    LZWByte = clearCode
    LZWBitPos = codeLen
    while LZWBitPos >= 8:
        yield LZWByte & 0xff
        LZWByte >>= 8
        LZWBitPos -= 8

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

        # yield code
        LZWByte |= code << LZWBitPos
        LZWBitPos += codeLen
        while LZWBitPos >= 8:
            yield LZWByte & 0xff
            LZWByte >>= 8
            LZWBitPos -= 8

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
                # yield clear code
                LZWByte |= clearCode << LZWBitPos
                LZWBitPos += codeLen
                while LZWBitPos >= 8:
                    yield LZWByte & 0xff
                    LZWByte >>= 8
                    LZWBitPos -= 8
                # initialize dictionary
                LZWDict = dict((bytes((i,)), i) for i in range(palSize))
                codeLen = minCodeLen

    # yield end code
    LZWByte |= endCode << LZWBitPos
    LZWBitPos += codeLen
    while LZWBitPos > 0:
        yield LZWByte & 0xff
        LZWByte >>= 8
        LZWBitPos -= 8

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

def raw_image_to_GIF(rawHandle, width, GIFHandle):
    """Convert raw RGB image (bytes: RGBRGB...) into GIF."""

    (height, remainder) = divmod(rawHandle.seek(0, 2), width * 3)

    if remainder:
        sys.exit("Input file size is not a multiple of (width * 3).")
    if height == 0:
        sys.exit("Input file is empty.")
    if height > 65535:
        sys.exit("Output file would become too tall.")

    palette = get_palette_from_raw_image(rawHandle)
    imageData = bytes(raw_image_to_indexed(rawHandle, palette))
    LZWData = bytes(encode_LZW_data(palette, imageData))
    write_GIF(width, height, palette, LZWData, GIFHandle)

# --- Main ----------------------------------------------------------------------------------------

def main():
    if len(sys.argv) == 3:
        decode = True
        (source, target) = sys.argv[1:]
    elif len(sys.argv) == 4:
        decode = False
        (source, width, target) = sys.argv[1:]
        try:
            width = int(width, 10)
            if not 1 <= width <= 65535:
                raise ValueError
        except ValueError:
            sys.exit("Width must be 1...65535.")
    else:
        exit(HELP_TEXT)

    if not os.path.isfile(source):
        sys.exit("Input file not found.")
    if os.path.exists(target):
        sys.exit("Output file already exists.")

    try:
        with open(source, "rb") as sourceHnd, open(target, "wb") as targetHnd:
            if decode:
                GIF_to_raw_image(sourceHnd, targetHnd)
            else:
                raw_image_to_GIF(sourceHnd, width, targetHnd)
    except OSError:
        exit("Error reading/writing files.")

if __name__ == "__main__":
    main()

