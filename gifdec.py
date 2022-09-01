# a GIF decoder in pure Python

import argparse, os, struct, sys, time

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Convert a GIF file into a raw RGB image file."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print more info."
    )
    parser.add_argument(
        "input_file",
        help="GIF file to read. Only the first image will be read."
    )
    parser.add_argument(
        "output_file",
        help="Raw RGB image file to write. Format: 3 bytes (red, green, blue) "
        "per pixel; order of pixels: first right, then down; file extension "
        "'.data' in GIMP."
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input_file):
        sys.exit("Input file not found.")
    if os.path.exists(args.output_file):
        sys.exit("Output file already exists.")

    return args

def get_bytes(handle, length):
    # read bytes from file
    data = handle.read(length)
    if len(data) < length:
        sys.exit("Unexpected end of file.")
    return data

def generate_subblocks(handle):
    # generate data from GIF subblocks
    sbSize = get_bytes(handle, 1)[0]  # subblock size
    while sbSize:
        chunk = get_bytes(handle, sbSize + 1)  # subblock & size of next one
        yield chunk[:-1]
        sbSize = chunk[-1]

def get_image_info(handle):
    # read information of one image in GIF file
    # handle position must be at first byte after ',' of Image Descriptor
    # return a dict with these keys:
    #     width:      image width
    #     height:     image height
    #     interlace:  is image data stored in interlaced format? (bool)
    #     lctAddr:    Local Color Table address (None = no LCT)
    #     lctBits:    Local Color Table bit depth (None = no LCT)
    #     lzwPalBits: palette bit depth in LZW encoding
    #     lzwAddr:    LZW data address

    (width, height, miscFields) = struct.unpack("<4x2HB", get_bytes(handle, 9))
    if min(width, height) == 0:
        sys.exit("Image area is zero.")

    if miscFields & 0b10000000:
        # has Local Color Table
        lctAddr = handle.tell()
        lctBits = (miscFields & 0b00000111) + 1
        get_bytes(handle, 2 ** lctBits * 3)  # skip bytes
    else:
        # no Local Color Table
        lctAddr = None
        lctBits = None

    lzwPalBits = get_bytes(handle, 1)[0]
    if not 2 <= lzwPalBits <= 11:
        sys.exit("Invalid LZW palette bit depth.")

    return {
        "width":      width,
        "height":     height,
        "interlace":  bool(miscFields & 0b01000000),
        "lctAddr":    lctAddr,
        "lctBits":    lctBits,
        "lzwPalBits": lzwPalBits,
        "lzwAddr":    handle.tell(),
    }

def skip_extension_block(handle):
    # skip Extension block in GIF file;
    # handle position must be at first byte after Extension Introducer ('!')

    label = get_bytes(handle, 1)[0]
    if label in (0x01, 0xf9, 0xff):
        # Plain Text Extension, Graphic Control Extension, Application Ext.
        get_bytes(handle, get_bytes(handle, 1)[0])  # skip bytes
        all(generate_subblocks(handle))  # skip subblocks
    elif label == 0xfe:
        # Comment Extension
        all(generate_subblocks(handle))  # skip subblocks
    else:
        sys.exit("Invalid Extension label.")

def get_first_image_info(handle):
    # return get_image_info() for first image in GIF file, or None if there
    # are no images;
    # ignore any extension blocks before the image;
    # handle position must be at first byte after Global Color Table (or after
    # Logical Screen Descriptor if there's no Global Color Table)

    while True:
        blockType = get_bytes(handle, 1)
        if blockType == b",":  # Image Descriptor
            return get_image_info(handle)
        elif blockType == b"!":  # Extension
            skip_extension_block(handle)
        elif blockType == b";":  # Trailer
            return None
        else:
            sys.exit("Invalid block type.")

def get_gif_info(handle):
    # read a GIF file; return info of first image as a dict with these keys:
    #     width, height, interlace, lzwPalBits, lzwAddr: see get_image_info()
    #     palAddr: palette (Local/Global Color Table) address
    #     palBits: palette (Local/Global Color Table) bit depth

    handle.seek(0)

    # Header
    (id_, version) = struct.unpack("3s3s", get_bytes(handle, 6))
    if id_ != b"GIF":
        sys.exit("Not a GIF file.")
    if version not in (b"87a", b"89a"):
        print("Warning: unknown GIF version.", file=sys.stderr)

    # Logical Screen Descriptor
    packedFields = struct.unpack("4xB2x", get_bytes(handle, 7))[0]
    if packedFields & 0b10000000:
        # has Global Color Table
        palAddr = handle.tell()
        palBits = (packedFields & 0b00000111) + 1
        get_bytes(handle, 2 ** palBits * 3)  # skip bytes
    else:
        # no Global Color Table
        palAddr = None
        palBits = None

    imageInfo = get_first_image_info(handle)
    if imageInfo is None:
        sys.exit("No images in file.")

    if imageInfo["lctAddr"] is not None:
        # use Local instead of Global Color Table
        palAddr = imageInfo["lctAddr"]
        palBits = imageInfo["lctBits"]
    elif palAddr is None:
        # no Local/Global Color Table
        sys.exit("No palette for first image.")

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
    # decode Lempel-Ziv-Welch (LZW) data (bytes)
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

    # LZW dictionary: index = code, value = entry (reference to another code,
    # final byte)
    lzwDict = [(None, i) for i in range(2 ** palBits + 2)]

    while True:
        # get current LZW code (0-4095) from remaining data:
        # 1) get the 1-3 bytes that contain the code; equivalent to:
        # codeByteCnt = ceil((bitPos + codeLen) / 8)
        codeByteCnt = (bitPos + codeLen + 7) // 8
        if pos + codeByteCnt > len(data):
            sys.exit("Unexpected end of file.")
        codeBytes = data[pos:pos+codeByteCnt]
        # 2) convert the bytes into an integer (first byte = least significant)
        code = sum(b << (i * 8) for (i, b) in enumerate(codeBytes))
        # 3) delete previously-read bits from the end and unnecessary bits
        # from the beginning; equivalent to:
        # code = (code >> bitPos) % 2 ** codeLen
        code = (code >> bitPos) & ((1 << codeLen) - 1)

        # advance byte/bit position so the next code can be read correctly
        bitPos += codeLen
        pos += bitPos >> 3  # pos += bitPos // 8
        bitPos &= 0b111     # bitPos %= 8

        # update statistics
        codeCount += 1
        bitCount += codeLen

        if code == clearCode:
            # LZW clear code:
            # reset dict. & code length; don't add dict. entry with next code
            lzwDict = lzwDict[:2**palBits+2]
            codeLen = palBits + 1
            prevCode = None
        elif code == endCode:
            break
        elif code > len(lzwDict):
            sys.exit("Invalid LZW code.")
        else:
            # dictionary entry
            if prevCode is not None:
                # add new entry (previous code, first byte of current/previous
                # entry)
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
        print(
            f"LZW data: {codeCount} codes, {bitCount} bits, {len(imageData)} "
            "pixels"
        )

    return imageData

def deinterlace(imageData, width):
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

def main():
    startTime = time.time()
    args = parse_arguments()

    # get palette and LZW image data from input file
    try:
        with open(args.input_file, "rb") as handle:
            gifInfo = get_gif_info(handle)
            handle.seek(gifInfo["palAddr"])
            palette = get_bytes(handle, 2 ** gifInfo["palBits"] * 3)
            handle.seek(gifInfo["lzwAddr"])
            imageData = b"".join(generate_subblocks(handle))
    except OSError:
        sys.exit("Error reading input file.")

    if args.verbose:
        print(
            os.path.basename(args.input_file) + ":",
            ", ".join(f"{k}={gifInfo[k]}" for k in sorted(gifInfo))
        )

    # decode and deinterlace image data
    imageData = lzw_decode(imageData, gifInfo["lzwPalBits"], args)
    if max(imageData) >= 2 ** gifInfo["palBits"]:
        sys.exit("Invalid index in image data.")
    if gifInfo["interlace"]:
        imageData = b"".join(deinterlace(imageData, gifInfo["width"]))

    # tuple of bytestrings
    palette = tuple(palette[i:i+3] for i in range(0, len(palette), 3))

    # write output file
    try:
        with open(args.output_file, "wb") as handle:
            handle.seek(0)
            handle.write(b"".join(palette[i] for i in imageData))
    except OSError:
        sys.exit("Error writing output file.")

    if args.verbose:
        print(f"time: {time.time()-startTime:.1f} s")

main()
