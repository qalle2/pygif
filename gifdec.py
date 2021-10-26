# a GIF decoder
# acronyms:
#     GCT = Global Color Table
#     LCT = Local Color Table
#     LSD = Logical Screen Descriptor
#     LZW = Lempel-Ziv-Welch

import argparse, math, os, struct, sys, time

BITS_PER_BYTE = 8

class GifError(Exception):
    # exception for GIF-related errors
    pass

def parse_arguments():
    # parse command line arguments using argparse

    parser = argparse.ArgumentParser(
        description="Decode a GIF file into raw RGB data (bytes: RGBRGB...; order of pixels: "
        "first right, then down; file extension '.data' in GIMP)."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print more info."
    )
    parser.add_argument(
        "input_file", help="GIF file to read."
    )
    parser.add_argument(
        "output_file", help="Raw RGB data file to write."
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found.")
    if os.path.exists(args.output_file):
        sys.exit("Output file already exists.")

    return args

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
        lctBits = (packedFields & 0x07) + 1
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
        palBits = (packedFields & 0x07) + 1
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

def lzw_decode(data, palBits, args):
    # decode LZW data (bytes)
    # palBits: palette bit depth in LZW encoding (2-8)
    # return: indexed image data (bytes)

    pos       = 0                 # byte position in LZW data
    bitPos    = 0                 # bit position within LZW data byte (0-7)
    codeLen   = palBits + 1       # current length of LZW codes, in bits (3-12)
    code      = 0                 # current LZW code (0-4095)
    prevCode  = None              # previous code for dictionary entry or None
    clearCode = 2 ** palBits      # LZW clear code
    endCode   = 2 ** palBits + 1  # LZW end code
    entry     = bytearray()       # reconstructed dictionary entry
    imageData = bytearray()       # decoded image data
    codeCount = 0                 # number of LZW codes read (statistics only)
    bitCount  = 0                 # number of LZW bits read (statistics only)

    # LZW dictionary: index = code, value = entry (reference to another code, final byte)
    lzwDict = [(None, i) for i in range(2 ** palBits + 2)]

    while True:
        # get current LZW code (0-4095) from remaining data:
        # 1) get the 1-3 bytes that contain the code
        codeByteCnt = math.ceil((bitPos + codeLen) / BITS_PER_BYTE)
        if pos + codeByteCnt > len(data):
            raise GifError("unexpected end of file")
        codeBytes = data[pos:pos+codeByteCnt]
        # 2) convert the bytes into an unsigned integer (first byte = least significant)
        code = sum(b << (i * BITS_PER_BYTE) for (i, b) in enumerate(codeBytes))
        # 3) delete previously-read bits from the end and unnecessary bits from the beginning
        code = (code >> bitPos) % 2 ** codeLen

        # advance byte/bit position so the next code can be read correctly
        bitPos += codeLen
        pos += bitPos // BITS_PER_BYTE
        bitPos %= BITS_PER_BYTE

        # update statistics
        codeCount += 1
        bitCount += codeLen

        if code == clearCode:
            # LZW clear code:
            # reset dictionary and code length; don't add a dictionary entry with next code
            lzwDict = lzwDict[:2**palBits+2]
            codeLen = palBits + 1
            prevCode = None
        elif code == endCode:
            # LZW end code: stop decoding
            break
        elif code > len(lzwDict):
            # invalid code
            raise GifError("invalid LZW code")
        else:
            # dictionary entry
            if prevCode is not None:
                # add new entry (previous code, first byte of current/previous entry)
                suffixCode = code if code < len(lzwDict) else prevCode
                while suffixCode is not None:
                    (suffixCode, suffixByte) = lzwDict[suffixCode]
                lzwDict.append((prevCode, suffixByte))
                prevCode = None
            # reconstruct and store entry
            entry.clear()
            referredCode = code
            while referredCode is not None:
                (referredCode, byte) = lzwDict[referredCode]
                entry.append(byte)
            entry.reverse()
            imageData.extend(entry)
            # prepare to add a dictionary entry
            if len(lzwDict) < 2 ** 12:
                prevCode = code
            if len(lzwDict) == 2 ** codeLen and codeLen < 12:
                codeLen += 1

    if args.verbose:
        print(f"lzwCodes={codeCount}, lzwBits={bitCount}, pixels={len(imageData)}")

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

def main():
    startTime = time.time()
    args = parse_arguments()

    try:
        with open(args.input_file, "rb") as source, open(args.output_file, "wb") as target:
            decode_gif(source, target, args)
    except OSError:
        sys.exit("Error reading/writing files.")
    except GifError as error:
        sys.exit(f"Error in GIF file: {error}")

    if args.verbose:
        print(f"time={time.time()-startTime:.1f}")

if __name__ == "__main__":
    main()
