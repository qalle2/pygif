# a GIF encoder in pure Python

import argparse, math, os, struct, sys, time

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Convert a raw RGB image file into a GIF file."
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
        "input_file", help="Raw RGB image file to read. Format: 3 bytes (red, green, blue) per "
        "pixel; order of pixels: first right, then down; file extension '.data' in GIMP. 256 "
        "unique colors or less."
    )
    parser.add_argument(
        "width", type=int, help="Width of input_file in pixels."
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
    # encode image data using LZW (Lempel-Ziv-Welch)
    # palBits:   palette bit depth in encoding (2-8)
    # imageData: indexed image data (1 byte/pixel)
    # generate:  (code, code_length_in_bits)

    # TODO: find out why this function encodes wolf3.gif and wolf4.gif different from GIMP.

    # LZW dictionary (key = LZW entry, value = LZW code)
    # note: doesn't contain clear and end codes, so actual length is len() + 2
    # note: uses a lot of memory but looking up an entry is fast
    lzwDict = dict((bytes((i,)), i) for i in range(2 ** palBits))

    pos     = 0            # position in input data
    codeLen = palBits + 1  # length of LZW codes (3-12)
    entry   = bytearray()  # dictionary entry

    yield (2 ** palBits, codeLen)  # clear code

    while pos < len(imageData):
        # find longest entry that's a prefix of remaining input data, and corresponding code
        # note: [pos:pos+1] instead of [pos:] breaks some decoders, investigate further?
        entry.clear()
        for byte in imageData[pos:]:
            entry.append(byte)
            try:
                code = lzwDict[bytes(entry)]
            except KeyError:
                entry = entry[:-1]
                break

        yield (code, codeLen)  # code for entry

        # advance in input data; if there's data left, update dictionary
        pos += len(entry)
        if pos < len(imageData):
            if len(lzwDict) < 2 ** 12 - 2:
                # dictionary not full; add an entry (current entry plus next pixel);
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

    yield (2 ** palBits + 1, codeLen)  # end code

def generate_lzw_bytes(paletteBits, imageData, args):
    # get LZW codes, generate LZW data bytes

    data    = 0  # LZW codes to convert into bytes (max. 7 + 12 = 19 bits)
    dataLen = 0  # data length in bits

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
        print(f"LZW data: {codeCount} codes, {totalCodeLen} bits")

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

    # process input file
    try:
        # validate size
        size = os.path.getsize(args.input_file)
        (height, remainder) = divmod(size, args.width * 3)
        if remainder or not 1 <= height <= 0xffff:
            sys.exit("Invalid input file size.")
        # get palette and indexed image data
        with open(args.input_file, "rb") as handle:
            palette = get_palette(handle)
            imageData = raw_image_to_indexed(handle, palette)
    except OSError:
        sys.exit("Error reading input file.")

    if args.verbose:
        print("read {}: {}*{} pixels, {} unique color(s)".format(
            os.path.basename(args.input_file), args.width, height, len(palette) // 3
        ))

    # write output file
    try:
        with open(args.output_file, "wb") as handle:
            handle.seek(0)
            for chunk in generate_gif(palette, imageData, args):
                handle.write(chunk)
            size = handle.seek(0, 2)
    except OSError:
        sys.exit("Error writing output file.")

    if args.verbose:
        print("wrote {}: {} bytes; time {:.1f} s".format(
            os.path.basename(args.output_file), size, time.time() - startTime
        ))

main()
