# a GIF encoder
# acronyms:
#     GCT = Global Color Table
#     LCT = Local Color Table
#     LSD = Logical Screen Descriptor
#     LZW = Lempel-Ziv-Welch

import argparse, math, os, struct, sys, time

class RgbError(Exception):
    # exception for errors related to raw RGB files
    pass

def parse_arguments():
    # parse command line arguments using argparse

    parser = argparse.ArgumentParser(
        description="Encode a GIF file from raw RGB data (bytes: RGBRGB...; order of pixels: "
        "first right, then down; file extension '.data' in GIMP)."
    )

    parser.add_argument(
        "-w", "--width", type=int, required=True, help="Width of input file in pixels. Required."
    )
    parser.add_argument(
        "-r", "--no-dict-reset", action="store_true",
        help="Don't reset the LZW dictionary when it fills up. May compress highly repetitive "
        "images better."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print more info."
    )
    parser.add_argument(
        "input_file", help="Raw RGB data file to read."
    )
    parser.add_argument(
        "output_file", help="GIF file to write."
    )

    args = parser.parse_args()

    if not 1 <= args.width <= 0xffff:
        sys.exit("Invalid width.")

    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found.")
    if os.path.exists(args.output_file):
        sys.exit("Output file already exists.")

    return args

def get_palette_from_raw_image(handle):
    # create palette (bytes, RGBRGB...) from raw RGB image

    pixelCount = handle.seek(0, 2) // 3
    handle.seek(0)
    palette = set()

    for i in range(pixelCount):
        palette.add(handle.read(3))
        if len(palette) > 256:
            raise RgbError("too many colors")

    return b"".join(sorted(palette))

def raw_image_to_indexed(handle, palette):
    # convert raw RGB image into indexed data (1 byte/pixel) using palette (RGBRGB...)

    pixelCount = handle.seek(0, 2) // 3
    handle.seek(0)
    rgbToIndex = dict((palette[i*3:(i+1)*3], i) for i in range(len(palette) // 3))
    indexedData = bytearray()

    for i in range(pixelCount):
        indexedData.append(rgbToIndex[handle.read(3)])

    return indexedData

def get_palette_bit_depth(colorCount):
    # how many bits needed for palette
    assert 1 <= colorCount <= 256
    return max(math.ceil(math.log2(colorCount)), 1)

def lzw_encode(palBits, imageData, args):
    # LZW encode image data (1 byte/pixel)
    # palBits: palette bit depth in encoding (2-8)
    # generate: (LZW_code, LZW_code_length_in_bits)

    # TODO: find out why this function encodes wolf3.gif and wolf4.gif different from GIMP.

    # LZW dictionary (key = LZW entry, value = LZW code)
    # note: doesn't contain clear and end codes, so actual length is len() + 2
    # note: uses a lot of memory but looking up an entry is fast
    lzwDict = dict((bytes((i,)), i) for i in range(2 ** palBits))

    pos     = 0            # position in input data
    codeLen = palBits + 1  # length of LZW codes (3-12)
    entry   = bytearray()  # dictionary entry

    # output clear code
    yield (2 ** palBits, codeLen)

    while pos < len(imageData):
        # find longest entry that's prefix of remaining input data, and corresponding code
        # note: [pos:pos+1] instead of [pos:] breaks some decoders, investigate further?
        entry.clear()
        for byte in imageData[pos:]:
            entry.append(byte)
            try:
                code = lzwDict[bytes(entry)]
            except KeyError:
                entry = entry[:-1]
                break

        # output code for entry
        yield (code, codeLen)

        # advance in input data; if there's data left, update dictionary
        pos += len(entry)
        if pos < len(imageData):
            if len(lzwDict) < 2 ** 12 - 2:
                # dictionary not full; add entry (current entry plus next pixel);
                # increase code length if necessary
                entry.append(imageData[pos])
                lzwDict[bytes(entry)] = len(lzwDict) + 2
                if len(lzwDict) > 2 ** codeLen - 2:
                    codeLen += 1
            elif not args.no_dict_reset:
                # dictionary full; output clear code; reset code length and dictionary
                yield (2 ** palBits, codeLen)
                codeLen = palBits + 1
                lzwDict = dict((bytes((i,)), i) for i in range(2 ** palBits))

    # output end code
    yield (2 ** palBits + 1, codeLen)

def lzw_codes_to_bytes(paletteBits, imageData, args):
    # get LZW codes, return LZW data bytes

    data      = 0            # LZW codes to convert into bytes
    dataLen   = 0            # number of bits in data (max. 7 + 12 = 19)
    dataBytes = bytearray()

    codeCount    = 0  # codes written
    totalCodeLen = 0  # bits written

    for (code, codeLen) in lzw_encode(paletteBits, imageData, args):
        # prepend code to data
        data |= code << dataLen
        dataLen += codeLen
        # chop off full bytes from end of data
        while dataLen >= 8:
            dataBytes.append(data & 0xff)
            data >>= 8
            dataLen -= 8
        # update stats
        codeCount += 1
        totalCodeLen += codeLen

    if dataLen:
        # output last byte
        dataBytes.append(data)

    if args.verbose:
        print(f"pixels={len(imageData)}, lzwCodes={codeCount}, lzwBits={totalCodeLen}")

    return dataBytes

def write_gif(width, height, palette, lzwData, handle):
    # write a GIF file (version 87a, with GCT, one image)
    # palette: bytes RGBRGB..., lzwData: bytes

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
        sbSize = min(0xff, len(lzwData) - pos)  # subblock size
        handle.write(bytes((sbSize,)) + lzwData[pos:pos+sbSize])
        pos += sbSize

    # empty subblock and Trailer
    handle.write(b"\x00;")

def encode_gif(rawHandle, gifHandle, args):
    # convert raw RGB image (bytes: RGBRGB...) into GIF

    (height, remainder) = divmod(rawHandle.seek(0, 2), args.width * 3)
    if remainder or not 1 <= height <= 0xffff:
        raise RgbError("invalid file size")

    palette = get_palette_from_raw_image(rawHandle)
    if args.verbose:
        print(f"width={args.width}, {height=}, uniqueColors={len(palette)//3}")
    imageData = raw_image_to_indexed(rawHandle, palette)
    lzwPalBits = max(get_palette_bit_depth(len(palette) // 3), 2)
    lzwData = lzw_codes_to_bytes(lzwPalBits, imageData, args)
    write_gif(args.width, height, palette, lzwData, gifHandle)

def main():
    startTime = time.time()
    args = parse_arguments()

    try:
        with open(args.input_file, "rb") as source, open(args.output_file, "wb") as target:
            encode_gif(source, target, args)
    except OSError:
        sys.exit("Error reading/writing files.")
    except RgbError as error:
        sys.exit(f"Error in raw RGB data file: {error}")

    if args.verbose:
        print(f"time={time.time()-startTime:.1f}")

if __name__ == "__main__":
    main()
