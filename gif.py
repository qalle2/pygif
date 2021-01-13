"""GIF decoder/encoder in pure Python.

Acronyms:
    GCT = Global Color Table
    LCT = Local Color Table
    LSD = Logical Screen Descriptor
    LZW = Lempel-Ziv-Welch"""

import argparse
import math
import os
import struct
import sys

class GifError(Exception):
    """An exception for GIF-related errors."""

class RgbError(Exception):
    """An exception for errors related to raw RGB files."""

# --- Decoding ------------------------------------------------------------------------------------

def read_bytes(handle, length):
    """Read bytes from file."""

    data = handle.read(length)
    if len(data) < length:
        raise GifError("EOF")
    return data

def skip_bytes(handle, length):
    """Skip bytes in file."""

    origPos = handle.tell()
    handle.seek(length, 1)
    if handle.tell() - origPos < length:
        raise GifError("EOF")

def read_subblocks(handle):
    """Generate data from GIF subblocks."""

    sbSize = read_bytes(handle, 1)[0]
    while sbSize:
        chunk = read_bytes(handle, sbSize + 1)
        yield chunk[:-1]
        sbSize = chunk[-1]

def skip_subblocks(handle):
    """Skip GIF subblocks."""

    sbSize = read_bytes(handle, 1)[0]
    while sbSize:
        skip_bytes(handle, sbSize)
        sbSize = read_bytes(handle, 1)[0]

def read_image_info(handle):
    """Read information of one image in GIF file.
    Handle position must be at first byte after "," of Image Descriptor."""

    (width, height, packedFields) = struct.unpack("<4x2HB", read_bytes(handle, 9))
    if min(width, height) == 0:
        raise GifError("IMAGE_AREA_ZERO")

    if packedFields >> 7:  # LCT?
        lctAddr = handle.tell()
        lctBits = (packedFields & 7) + 1
        skip_bytes(handle, 2 ** lctBits * 3)
    else:
        lctAddr = None
        lctBits = None

    lzwPalBits = read_bytes(handle, 1)[0]
    if not 2 <= lzwPalBits <= 11:
        raise GifError("INVALID_LZW_PALETTE_BIT_DEPTH")

    return {
        "width":      width,
        "height":     height,
        "interlace":  bool((packedFields >> 6) & 1),  # image data interlaced?
        "lctAddr":    lctAddr,        # LCT address or None
        "lctBits":    lctBits,        # LCT bit depth or None
        "lzwPalBits": lzwPalBits,     # palette bit depth in LZW encoding
        "lzwAddr":    handle.tell(),  # LZW data address
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
        raise GifError("INVALID_EXTENSION_LABEL")
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
            raise GifError("INVALID_BLOCK_TYPE")

def read_gif(handle):
    """Read information of GIF file (first image only)."""

    handle.seek(0)

    # Header and LSD
    (id_, version, packedFields) = struct.unpack("<3s3s4xB2x", read_bytes(handle, 13))

    if id_ != b"GIF":
        raise GifError("NOT_A_GIF_FILE")
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
        raise GifError("NO_IMAGES_IN_FILE")

    if imageInfo["lctAddr"] is not None:
        # use LCT instead of GCT
        palAddr = imageInfo["lctAddr"]
        palBits = imageInfo["lctBits"]
    elif palAddr is None:
        raise GifError("NO_PALETTE")

    return {
        "width":      imageInfo["width"],
        "height":     imageInfo["height"],
        "interlace":  imageInfo["interlace"],   # image data interlaced?
        "palAddr":    palAddr,                  # palette address
        "palBits":    palBits,                  # palette bit depth
        "lzwPalBits": imageInfo["lzwPalBits"],  # palette bit depth in LZW encoding
        "lzwAddr":    imageInfo["lzwAddr"],     # LZW data address
    }

def decode_lzw_data(LZW_DATA, PAL_BITS, ARGS):
    """Decode LZW data (bytes).
    PAL_BITS: palette bit depth in LZW encoding (2...8)
    ARGS: from argparse
    generate: indexed image data as bytes (1 byte/pixel)"""

    # Note: constants are named LIKE_THIS in this function.

    # constants
    MIN_CODE_LEN = PAL_BITS + 1       # initial length of LZW codes (3...9)
    MAX_CODE_LEN = 12                 # maximum length of LZW codes
    PAL_SIZE     = 1 << PAL_BITS      # number of palette indexes in LZW encoding
    CLEAR_CODE   = PAL_SIZE           # LZW clear code
    END_CODE     = PAL_SIZE + 1       # LZW end code
    MIN_DICT_LEN = PAL_SIZE + 2       # initial length of LZW dictionary
    MAX_DICT_LEN = 1 << MAX_CODE_LEN  # maximum length of LZW dictionary

    # variables
    pos         = 0               # number of bytes completely read from LZW data
    bitPos      = 0               # number of bits read from next byte in LZW data
    codeLen     = MIN_CODE_LEN    # length of LZW codes
    maxDictLen  = 1 << codeLen    # maximum number of codes *with current codeLen*
    codeBitmask = maxDictLen - 1  # AND bitmask for reading codes
    entry       = bytearray()     # entry to output
    # LZW dictionary; index: code, value: entry (reference to another code, final byte)
    lzwDict = [(-1, i) for i in range(MIN_DICT_LEN)]

    while True:
        # read next code from remaining LZW data
        # combine 1...3 bytes in reverse order, e.g. 0xab 0xcd -> 0xcdab
        code = 0
        shiftCount = 0
        for offset in range((bitPos + codeLen + 7) >> 3):  # ceil((bitPos + codeLen) / 8)
            try:
                code |= LZW_DATA[pos+offset] << shiftCount
            except IndexError:
                raise GifError("EOF")
            shiftCount += 8
        # delete previously-read bits from end and unnecessary bits from beginning
        code = (code >> bitPos) & codeBitmask
        if ARGS.log:
            print(format(code, f"0{codeLen}b"))

        # advance in LZW data
        bitPos += codeLen
        pos += bitPos >> 3
        bitPos &= 7

        if code == CLEAR_CODE:
            # reset code length
            codeLen     = MIN_CODE_LEN
            maxDictLen  = 1 << codeLen
            codeBitmask = maxDictLen - 1
            # reset dictionary
            lzwDict = lzwDict[:MIN_DICT_LEN]
            # don't add an entry to dictionary on next round
            prevCode = None
        elif code == END_CODE:
            break
        else:
            # dictionary entry
            if prevCode is not None:
                # entry to take first byte from for new dictionary entry
                if code < len(lzwDict):
                    suffixCode = code
                elif code == len(lzwDict):
                    suffixCode = prevCode
                else:
                    raise GifError("INVALID_LZW_CODE")
                # get first byte of entry
                while suffixCode != -1:
                    (suffixCode, suffixByte) = lzwDict[suffixCode]
                # add entry to dictionary
                lzwDict.append((prevCode, suffixByte))
                prevCode = None
            if code < len(lzwDict) < MAX_DICT_LEN:
                prevCode = code
            if len(lzwDict) == maxDictLen and codeLen < MAX_CODE_LEN:
                codeLen += 1
                maxDictLen  = 1 << codeLen
                codeBitmask = maxDictLen - 1
            # emit current entry
            entry.clear()
            while code != -1:
                (code, byte) = lzwDict[code]
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

def decode_gif(gifHandle, rawHandle, args):
    """Decode GIF into raw RGB data (bytes: RGBRGB...)."""

    info = read_gif(gifHandle)

    gifHandle.seek(info["palAddr"])
    palette = read_bytes(gifHandle, 2 ** info["palBits"] * 3)

    gifHandle.seek(info["lzwAddr"])
    imageData = b"".join(read_subblocks(gifHandle))

    # decode image data
    imageData = b"".join(decode_lzw_data(imageData, info["lzwPalBits"], args))
    if info["palBits"] < 8 and max(imageData) >= 2 ** info["palBits"]:
        raise GifError("INVALID_INDEX_IN_IMAGE_DATA")

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
            raise RgbError("TOO_MANY_COLORS")
    return b"".join(sorted(palette))

def raw_image_to_indexed(handle, palette):
    """Convert raw RGB image (bytes: RGBRGB...) into indexed image (1 byte/pixel)
    using palette (bytes: RGBRGB...). Generate 1 pixel per call."""

    rgbToIndex = dict((palette[i*3:(i+1)*3], i) for i in range(len(palette) // 3))
    for color in read_raw_image(handle):
        yield rgbToIndex[color]

def get_palette_bit_depth(colorCount):
    """How many bits needed for palette."""

    return max(math.ceil(math.log2(colorCount)), 1)

def encode_lzw_data(PALETTE, IMAGE_DATA, ARGS):
    """Encode image data (1 byte/pixel) using LZW and palette (bytes: RGBRGB...).
    ARGS: from argparse. Generate bytes."""

    # Note: constants are named LIKE_THIS in this function.
    # TODO: find out why this function encodes wolf3.gif and wolf4.gif different from GIMP.

    # constants
    # palette bit depth in encoding
    PAL_BITS     = max(get_palette_bit_depth(len(PALETTE) // 3), 2)
    MIN_CODE_LEN = PAL_BITS + 1       # minimum length of LZW codes
    MAX_CODE_LEN = 12                 # maximum length of LZW codes
    PAL_SIZE     = 1 << PAL_BITS      # length of palette
    CLEAR_CODE   = PAL_SIZE           # LZW clear code
    END_CODE     = PAL_SIZE + 1       # LZW end code
    MAX_DICT_LEN = 1 << MAX_CODE_LEN  # maximum length of LZW dictionary

    # variables
    inputPos   = 0             # position in input
    codeLen    = MIN_CODE_LEN  # length of LZW codes
    maxDictLen = 1 << codeLen  # maximum number of codes *with current codeLen*
    lzwByte    = 0             # next byte to output
    lzwBitPos  = 0             # number of bits in LZWByte
    entry      = bytearray()   # LZW dictionary entry
    # LZW dictionary: {entry: code, ...}; note: doesn't contain clear and end codes,
    # so the actual length is len() + 2
    lzwDict = dict((bytes((i,)), i) for i in range(PAL_SIZE))

    # output clear code
    lzwByte = CLEAR_CODE
    lzwBitPos = codeLen
    while lzwBitPos >= 8:
        yield lzwByte & 0xff
        lzwByte >>= 8
        lzwBitPos -= 8
    if ARGS.log:
        print(format(CLEAR_CODE, f"0{codeLen}b"))

    while inputPos < len(IMAGE_DATA):
        # find longest entry that's a prefix of remaining image data, and corresponding code
        entry.clear()
        for pos in range(inputPos, len(IMAGE_DATA)):
            entry.append(IMAGE_DATA[pos])
            try:
                code = lzwDict[bytes(entry)]
            except KeyError:
                entry = entry[:-1]
                break
        inputPos += len(entry)

        # output code
        lzwByte |= code << lzwBitPos
        lzwBitPos += codeLen
        while lzwBitPos >= 8:
            yield lzwByte & 0xff
            lzwByte >>= 8
            lzwBitPos -= 8
        if ARGS.log:
            print(format(code, f"0{codeLen}b"))

        if inputPos < len(IMAGE_DATA):
            if len(lzwDict) + 2 < MAX_DICT_LEN:
                # dictionary isn't full
                # add entry: current entry plus next pixel
                entry.append(IMAGE_DATA[inputPos])
                lzwDict[bytes(entry)] = len(lzwDict) + 2
                # increase code length if necessary
                if len(lzwDict) + 2 == maxDictLen + 1:
                    codeLen += 1
                    maxDictLen = 1 << codeLen
            else:
                # dictionary is full
                # output clear code
                lzwByte |= CLEAR_CODE << lzwBitPos
                lzwBitPos += codeLen
                while lzwBitPos >= 8:
                    yield lzwByte & 0xff
                    lzwByte >>= 8
                    lzwBitPos -= 8
                if ARGS.log:
                    print(format(CLEAR_CODE, f"0{codeLen}b"))
                # reset code length
                codeLen = MIN_CODE_LEN
                maxDictLen = 1 << codeLen
                # reset dictionary
                lzwDict = dict((bytes((i,)), i) for i in range(PAL_SIZE))

    # output end code
    lzwByte |= END_CODE << lzwBitPos
    lzwBitPos += codeLen
    while lzwBitPos > 0:
        yield lzwByte & 0xff
        lzwByte >>= 8
        lzwBitPos -= 8
    if ARGS.log:
        print(format(END_CODE, f"0{codeLen}b"))

def write_gif(width, height, palette, lzwData, handle):
    """Write a GIF file (version 87a, with GCT, one image).
    palette: bytes RGBRGB..., lzwData: bytes"""

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
    while pos < len(lzwData):
        sbSize = min(0xff, len(lzwData) - pos)
        handle.write(bytes((sbSize,)) + lzwData[pos:pos+sbSize])
        pos += sbSize

    # empty subblock and Trailer
    handle.write(b"\x00;")

def encode_gif(rawHandle, gifHandle, args):
    """Convert raw RGB image (bytes: RGBRGB...) into GIF.
    args: from argparse"""

    (height, remainder) = divmod(rawHandle.seek(0, 2), args.width * 3)

    if remainder:
        raise RgbError("FILE_SIZE_NOT_DIVISIBLE_BY_WIDTH_TIMES_THREE")
    if height == 0:
        raise RgbError("FILE_EMPTY")
    if height > 0xffff:
        raise RgbError("IMAGE_TOO_TALL")

    palette = get_palette_from_raw_image(rawHandle)
    imageData = bytes(raw_image_to_indexed(rawHandle, palette))
    lzwData = bytes(encode_lzw_data(palette, imageData, args))
    write_gif(args.width, height, palette, lzwData, gifHandle)

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
        elif not 1 <= args.width <= 0xffff:
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
                decode_gif(sourceHnd, targetHnd, args)
            else:
                encode_gif(sourceHnd, targetHnd, args)
    except OSError:
        sys.exit("Error reading/writing files.")
    except GifError as error:
        sys.exit(f"GIF error: {error}")
    except RgbError as error:
        sys.exit(f"Raw RGB data error: {error}")

if __name__ == "__main__":
    main()

