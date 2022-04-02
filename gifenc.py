# a GIF encoder
# acronyms:
#     GCT = Global Color Table
#     LCT = Local Color Table
#     LSD = Logical Screen Descriptor
#     LZW = Lempel-Ziv-Welch

import argparse, math, os, struct, sys, time

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
        sys.exit("Invalid width argument.")
    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found.")
    if os.path.exists(args.output_file):
        sys.exit("Output file already exists.")

    return args

def get_palette(handle):
    # get palette from raw RGB image, return bytes (RGBRGB...)

    pixelCount = handle.seek(0, 2) // 3
    handle.seek(0)
    palette = {handle.read(3) for i in range(pixelCount)}
    if len(palette) > 256:
        sys.exit("Too many unique colors in input file.")
    return b"".join(sorted(palette))

def raw_image_to_indexed(handle, palette):
    # convert raw RGB image into indexed data (1 byte/pixel) using palette (RGBRGB...)

    pixelCount = handle.seek(0, 2) // 3
    handle.seek(0)
    rgbToIndex = dict((palette[i*3:(i+1)*3], i) for i in range(len(palette) // 3))
    return bytes(rgbToIndex[handle.read(3)] for i in range(pixelCount))

def generate_lzw_codes(palBits, imageData, args):
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

def generate_lzw_bytes(paletteBits, imageData, args):
    # get LZW codes, generate LZW data bytes

    data    = 0  # LZW codes to convert into bytes
    dataLen = 0  # number of bits in data (max. 7 + 12 = 19)

    codeCount    = 0  # codes written
    totalCodeLen = 0  # bits written

    for (code, codeLen) in generate_lzw_codes(paletteBits, imageData, args):
        # prepend code to data
        data |= code << dataLen
        dataLen += codeLen
        # chop off full bytes from end of data
        while dataLen >= 8:
            yield data & 0xff
            data >>= 8
            dataLen -= 8
        # update stats
        codeCount += 1
        totalCodeLen += codeLen

    if dataLen:
        yield data  # the last byte

    if args.verbose:
        print(f"pixels={len(imageData)}, lzwCodes={codeCount}, lzwBits={totalCodeLen}")

def generate_gif(palette, imageData, args):
    # generate a GIF file (version 87a, one image) as bytestrings
    # palette: 3 bytes/color, imageData: 1 byte/pixel

    height = len(imageData) // args.width  # image height

    # palette size in bits
    palBitsGct = max(math.ceil(math.log2(len(palette) // 3)), 1)  # in Global Color Table (1-8)
    palBitsLzw = max(palBitsGct, 2)                               # in LZW encoding (2-8)

    yield b"GIF87a"  # Header (signature, version)

    # Logical Screen Descriptor
    yield struct.pack(
        "<2H3B",
        args.width, height,           # logical screen width/height
        0b10000000 | palBitsGct - 1,  # packed fields (Global Color Table present)
        0, 0                          # background color index, aspect ratio
    )

    yield palette + (2 ** palBitsGct * 3 - len(palette)) * b"\x00"  # padded Global Color Table

    # Image Descriptor
    yield struct.pack(
        "<s4HB",
        b",", 0, 0,          # image separator, image left/top position
        args.width, height,  # image width/height
        0b00000000           # packed fields
    )

    yield bytes((palBitsLzw,))

    # LZW data in subblocks (length byte + 255 LZW bytes or less)
    subblock = bytearray()
    for lzwByte in generate_lzw_bytes(palBitsLzw, imageData, args):
        subblock.append(lzwByte)
        if len(subblock) == 0xff:
            # flush subblock
            yield bytes((len(subblock),)) + subblock
            subblock.clear()
    if subblock:
        yield bytes((len(subblock),)) + subblock  # the last subblock

    yield b"\x00;"  # empty subblock, trailer

def main():
    startTime = time.time()
    args = parse_arguments()

    try:
        # read input file
        with open(args.input_file, "rb") as source:
            (height, remainder) = divmod(source.seek(0, 2), args.width * 3)
            if remainder or not 1 <= height <= 0xffff:
                sys.exit("Invalid input file size.")
            palette = get_palette(source)
            imageData = raw_image_to_indexed(source, palette)
        # write output file
        with open(args.output_file, "wb") as target:
            target.seek(0)
            for chunk in generate_gif(palette, imageData, args):
                target.write(chunk)
    except OSError:
        sys.exit("Error reading/writing files.")

    if args.verbose:
        print(f"time={time.time()-startTime:.1f}")

main()
