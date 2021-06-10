# acronyms:
#     GCT = Global Color Table
#     LCT = Local Color Table
#     LSD = Logical Screen Descriptor
#     LZW = Lempel-Ziv-Welch

import argparse, math, os, struct, sys, time

class GifError(Exception):
    # exception for GIF-related errors
    pass

class RgbError(Exception):
    # exception for errors related to raw RGB files
    pass

def autodetect_operation(args):
    # autodetect whether to encode/decode based on file arguments

    isGif = tuple(
        os.path.splitext(f)[1].lower() == ".gif" for f in (args.input_file, args.output_file)
    )
    if isGif == (False, True):
        return "e"  # encode
    if isGif == (True, False):
        return "d"  # decode
    sys.exit("Could not autodetect operation.")

def parse_arguments():
    # parse command line arguments using argparse

    parser = argparse.ArgumentParser(
        description="Decode/encode a GIF file into/from raw RGB data (bytes: RGBRGB...;"
        " order of pixels: first right, then down; file extension '.data' in GIMP)."
    )

    parser.add_argument(
        "-o", "--operation", choices=("d", "e", "a"), default="a",
        help="What to do (d=decode, e=encode, a=autodetect; default=a)."
    )
    parser.add_argument(
        "-w", "--width", type=int, help="Width of input file in pixels (encoding only)."
    )
    parser.add_argument(
        "-r", "--no-dict-reset", action="store_true",
        help="When encoding, don't reset the LZW dictionary when it fills up."
        " May compress highly repetitive images better."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print more info."
    )
    parser.add_argument(
        "input_file", help="File to read."
    )
    parser.add_argument(
        "output_file", help="File to write."
    )

    args = parser.parse_args()

    if args.operation == "e" or args.operation == "a" and autodetect_operation(args) == "e":
        if args.width is None:
            sys.exit("-w/--width is required when encoding.")
        elif not 1 <= args.width <= 0xffff:
            sys.exit("Invalid width.")

    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found.")
    if os.path.exists(args.output_file):
        sys.exit("Output file already exists.")

    return args

# --- Decoding -------------------------------------------------------------------------------------

def read_bytes(handle, length):
    # read bytes from file
    data = handle.read(length)
    if len(data) < length:
        raise GifError("unexpected end of file")
    return data

def skip_bytes(handle, length):
    # skip bytes in file
    origPos = handle.tell()
    handle.seek(length, 1)
    if handle.tell() - origPos < length:
        raise GifError("unexpected end of file")

def read_subblocks(handle):
    # generate data from GIF subblocks
    sbSize = read_bytes(handle, 1)[0]  # size of first subblock
    while sbSize:
        chunk = read_bytes(handle, sbSize + 1)  # subblock, size of next subblock
        yield chunk[:-1]
        sbSize = chunk[-1]

def skip_subblocks(handle):
    # skip GIF subblocks
    sbSize = read_bytes(handle, 1)[0]
    while sbSize:
        skip_bytes(handle, sbSize)
        sbSize = read_bytes(handle, 1)[0]

def read_image_info(handle):
    # read information of one image in GIF file
    # handle position must be at first byte after ',' of Image Descriptor
    # return a dict with these keys:
    #     width:      image width
    #     height:     image height
    #     interlace:  is image data stored in interlaced format? (bool)
    #     lctAddr:    LCT address (None = no LCT)
    #     lctBits:    LCT bit depth (None = no LCT)
    #     lzwPalBits: palette bit depth in LZW encoding
    #     lzwAddr:    LZW data address

    (width, height, packedFields) = struct.unpack("<4x2HB", read_bytes(handle, 9))
    if min(width, height) == 0:
        raise GifError("image area zero")

    if packedFields & 0x80:
        # has LCT
        lctAddr = handle.tell()
        lctBits = (packedFields & 7) + 1
        skip_bytes(handle, 2 ** lctBits * 3)
    else:
        lctAddr = None
        lctBits = None

    lzwPalBits = read_bytes(handle, 1)[0]
    if not 2 <= lzwPalBits <= 11:
        raise GifError("invalid LZW palette bit depth")

    return {
        "width":      width,
        "height":     height,
        "interlace":  bool(packedFields & 0x40),
        "lctAddr":    lctAddr,
        "lctBits":    lctBits,
        "lzwPalBits": lzwPalBits,
        "lzwAddr":    handle.tell(),
    }

def skip_extension_block(handle):
    # skip Extension block in GIF file;
    # handle position must be at first byte after Extension Introducer ('!')

    label = read_bytes(handle, 1)[0]
    if label in (0x01, 0xf9, 0xff):
        # Plain Text Extension, Graphic Control Extension, Application Extension
        skip_bytes(handle, read_bytes(handle, 1)[0])
        skip_subblocks(handle)
    elif label == 0xfe:
        # Comment Extension
        skip_subblocks(handle)
    else:
        raise GifError("invalid Extension label")

def read_first_image_info(handle):
    # return read_image_info() for first image in GIF file, or None if there are no images;
    # ignore any extension blocks before the image;
    # handle position must be at first byte after GCT (or LSD if there's no GCT)

    while True:
        blockType = read_bytes(handle, 1)
        if blockType == b",":  # Image Descriptor
            return read_image_info(handle)
        elif blockType == b"!":  # Extension
            skip_extension_block(handle)
        elif blockType == b";":  # Trailer
            return None
        else:
            raise GifError("invalid block type")

def read_gif(handle):
    # read a GIF file; return info of first image as a dict with these keys:
    #     width:      see read_image_info()
    #     height:     see read_image_info()
    #     interlace:  see read_image_info()
    #     palAddr:    palette (LCT/GCT) address
    #     palBits:    palette (LCT/GCT) bit depth
    #     lzwPalBits: see read_image_info()
    #     lzwAddr:    see read_image_info()

    handle.seek(0)

    # Header and LSD
    (id_, version, packedFields) = struct.unpack("<3s3s4xB2x", read_bytes(handle, 13))

    if id_ != b"GIF":
        raise GifError("not a GIF file")
    if version not in (b"87a", b"89a"):
        print("Warning: unknown GIF version.", file=sys.stderr)

    if packedFields & 0x80:
        # has GCT
        palAddr = handle.tell()
        palBits = (packedFields & 7) + 1
        skip_bytes(handle, 2 ** palBits * 3)
    else:
        # no GCT
        palAddr = None
        palBits = None

    imageInfo = read_first_image_info(handle)
    if imageInfo is None:
        raise GifError("no images")

    if imageInfo["lctAddr"] is not None:
        # use LCT instead of GCT
        palAddr = imageInfo["lctAddr"]
        palBits = imageInfo["lctBits"]
    elif palAddr is None:
        # no LCT or GCT
        raise GifError("no palette")

    return {
        "width":      imageInfo["width"],
        "height":     imageInfo["height"],
        "interlace":  imageInfo["interlace"],
        "palAddr":    palAddr,
        "palBits":    palBits,
        "lzwPalBits": imageInfo["lzwPalBits"],
        "lzwAddr":    imageInfo["lzwAddr"],
    }

def lzw_bytes_to_codes(data, palBits):
    # decode LZW data (bytes);
    # palBits: palette bit depth in LZW encoding (2-8);
    # generate: (LZW_code, code_length_in_bits, code_for_previous_dictionary_entry)

    pos       = 0                 # number of bytes completely read from LZW data
    bitPos    = 0                 # number of bits read from next byte in LZW data
    codeLen   = palBits + 1       # length of LZW codes
    clearCode = 2 ** palBits      # LZW clear code
    endCode   = 2 ** palBits + 1  # LZW end code
    dictLen   = 2 ** palBits + 2  # length of simulated LZW dictionary
    prevCode  = None              # previous code for dictionary entry or None

    while True:
        # read next code from remaining data
        # combine 1-3 bytes in reverse order, e.g. 0xab 0xcd -> 0xcdab
        code = 0
        for offset in range((bitPos + codeLen + 7) // 8):  # ceil((bitPos + codeLen) / 8)
            try:
                code |= data[pos+offset] << (offset * 8)
            except IndexError:
                raise GifError("unexpected end of file")
        code >>= bitPos       # delete previously-read bits from end
        code %= 2 ** codeLen  # delete unnecessary bits from beginning

        # advance in data
        bitPos += codeLen
        pos += bitPos // 8
        bitPos %= 8

        yield (code, codeLen, prevCode)

        if code == clearCode:
            # reset code and dictionary length, don't add dictionary entry with next code
            codeLen = palBits + 1
            dictLen = 2 ** palBits + 2
            prevCode = None
        elif code == endCode:
            break
        else:
            # dictionary entry
            if prevCode is not None:
                # simulate adding a dictionary entry
                if code > dictLen:
                    raise GifError("invalid LZW code")
                dictLen += 1
                prevCode = None
            if code < dictLen < 2 ** 12:
                # prepare to add a dictionary entry
                prevCode = code
            if dictLen == 2 ** codeLen and codeLen < 12:
                codeLen += 1

def lzw_decode(data, palBits, args):
    # decode LZW data (bytes)
    # palBits: palette bit depth in LZW encoding (2-8)
    # return: indexed image data (bytes)

    clearCode = 2 ** palBits      # LZW clear code
    endCode   = 2 ** palBits + 1  # LZW end code
    entry     = bytearray()       # entry to output
    imageData = bytearray()       # decoded image data

    # stats
    codeCount    = 0  # codes read
    totalCodeLen = 0  # bits read

    # LZW dictionary: index = code, value = entry (reference to another code, final byte)
    lzwDict = [(-1, i) for i in range(2 ** palBits + 2)]

    # note: lzw_bytes_to_codes() does the dirty work
    for (code, codeLen, prevCode) in lzw_bytes_to_codes(data, palBits):
        codeCount += 1
        totalCodeLen += codeLen

        if code == clearCode:
            # reset dictionary
            lzwDict = lzwDict[:2**palBits+2]
        elif code != endCode:
            # dictionary entry
            if prevCode is not None:
                # add new entry (previous code, first byte of current/previous entry)
                suffixCode = code if code < len(lzwDict) else prevCode
                while suffixCode != -1:
                    (suffixCode, suffixByte) = lzwDict[suffixCode]
                lzwDict.append((prevCode, suffixByte))
            # get entry
            entry.clear()
            while code != -1:
                try:
                    (code, byte) = lzwDict[code]
                except IndexError:
                    raise GifError("invalid LZW code")
                entry.append(byte)
            entry.reverse()
            # add entry to output
            imageData.extend(entry)

    if args.verbose:
        print(f"lzwCodes={codeCount}, lzwBits={totalCodeLen}, pixels={len(imageData)}")

    return imageData

def deinterlace_image(imageData, width):
    # deinterlace image data (1 byte/pixel), generate one pixel row per call

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
    # decode GIF into raw RGB data (bytes: RGBRGB...)

    info = read_gif(gifHandle)

    gifHandle.seek(info["palAddr"])
    palette = read_bytes(gifHandle, 2 ** info["palBits"] * 3)

    gifHandle.seek(info["lzwAddr"])
    imageData = b"".join(read_subblocks(gifHandle))

    # decode image data
    imageData = lzw_decode(imageData, info["lzwPalBits"], args)
    if info["lzwPalBits"] > info["palBits"] and max(imageData) >= 2 ** info["palBits"]:
        raise GifError("invalid index in image data")

    if info["interlace"]:
        # deinterlace
        imageData = b"".join(deinterlace_image(imageData, info["width"]))

    # convert palette into a tuple of 3-byte colors
    palette = tuple(palette[pos:pos+3] for pos in range(0, len(palette), 3))

    # write raw RGB data
    rawHandle.seek(0)
    for i in imageData:
        rawHandle.write(palette[i])

# --- Encoding -------------------------------------------------------------------------------------

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

# --------------------------------------------------------------------------------------------------

def main():
    startTime = time.time()
    args = parse_arguments()

    if args.operation == "e" or args.operation == "a" and autodetect_operation(args) == "e":
        function = encode_gif
    else:
        function = decode_gif

    try:
        with open(args.input_file, "rb") as source, open(args.output_file, "wb") as target:
            function(source, target, args)
    except OSError:
        sys.exit("Error reading/writing files.")
    except GifError as error:
        sys.exit(f"Error in GIF file: {error}")
    except RgbError as error:
        sys.exit(f"Error in raw RGB data file: {error}")

    if args.verbose:
        print(f"time={time.time()-startTime:.1f}")

if __name__ == "__main__":
    main()
