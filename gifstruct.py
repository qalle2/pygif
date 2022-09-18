# print the high-level structure of a GIF file; under construction

import os, struct, sys

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

# -----------------------------------------------------------------------------

def read_header(handle):
    # read Header, Logical Screen Descriptor and Global Color Table from
    # current file position; return a dict

    # Header
    (id_, version) = struct.unpack("3s3s", get_bytes(handle, 6))
    if id_ != b"GIF":
        sys.exit("Not a GIF file.")

    # Logical Screen Descriptor (TODO: get more info)
    packedFields = struct.unpack("4xB2x", get_bytes(handle, 7))[0]
    if packedFields & 0b10000000:
        # has Global Color Table; skip it
        gctBits = (packedFields & 0b00000111) + 1
        get_bytes(handle, 2**gctBits * 3)
    else:
        # no Global Color Table
        gctBits = 0

    return {
        "version": version,
        "gctBits": gctBits,
    }

def read_image(handle):
    # read information of one image in GIF file
    # handle position must be at first byte after ',' of Image Descriptor
    # return a dict

    # TODO: get more info
    (width, height, miscFields) = struct.unpack("<4x2HB", get_bytes(handle, 9))
    if min(width, height) == 0:
        sys.exit("Image area is zero.")

    if miscFields & 0b10000000:
        # has Local Color Table
        lctBits = (miscFields & 0b00000111) + 1
        get_bytes(handle, 2 ** lctBits * 3)  # skip bytes
    else:
        # no Local Color Table
        lctBits = 0

    lzwPalBits = get_bytes(handle, 1)[0]
    lzwDataLen = sum(len(d) for d in generate_subblocks(handle))

    return {
        "width":      width,
        "height":     height,
        "interlace":  bool(miscFields & 0b01000000),
        "lctBits":    lctBits,
        "lzwPalBits": lzwPalBits,
        "lzwDataLen": lzwDataLen,
    }

def read_extension_block(handle):
    # read Extension block in GIF file;
    # handle position must be at first byte after Extension Introducer ('!')

    # TODO: print more info
    label = get_bytes(handle, 1)[0]
    print(f"    Label: 0x{label:02x}")
    if label in (0x01, 0xf9, 0xff):
        # Plain Text Extension, Graphic Control Extension, Application Ext.
        get_bytes(handle, get_bytes(handle, 1)[0])  # skip bytes
        all(generate_subblocks(handle))  # skip subblocks
    elif label == 0xfe:
        # Comment Extension
        all(generate_subblocks(handle))  # skip subblocks
    else:
        sys.exit("Invalid Extension label.")

def read_file(handle):
    handle.seek(0)
    fileInfo = read_header(handle)
    print(
        "Version:",
        fileInfo["version"].decode("ascii", errors="backslashreplace")
    )
    print("Global Color Table:",
        f"{2**fileInfo['gctBits']} colors" if fileInfo["gctBits"] else "none"
    )

    # read rest of blocks
    while True:
        print(f"At 0x{handle.tell():x}: ", end="")
        blockType = get_bytes(handle, 1)
        if blockType == b",":
            print(f"Image Descriptor:")
            imageInfo = read_image(handle)
            print("    width:", imageInfo["width"])
            print("    height:", imageInfo["height"])
            print("    interlace:", imageInfo["interlace"])
            print("    Local Color Table:",
                f"{2**fileInfo['lctBits']} colors" if imageInfo["lctBits"]
                else "none"
            )
            print(
                "    palette bit depth in LZW encoding:",
                imageInfo["lzwPalBits"]
            )
            print("    LZW data bytes:", imageInfo["lzwDataLen"])
        elif blockType == b"!":
            print(f"Extension:")
            read_extension_block(handle)
        elif blockType == b";":
            print(f"Trailer")
            break
        else:
            sys.exit(f"invalid block type 0x{blockType[0]:02x}")

def main():
    # parse command line argument
    if len(sys.argv) != 2:
        sys.exit(
            "Print the high-level structure of a GIF file. Argument: file to "
            "read."
        )
    filename = sys.argv[1]
    if not os.path.isfile(filename):
        sys.exit("Input file not found.")

    print("File:", os.path.basename(filename))

    try:
        with open(filename, "rb") as handle:
            read_file(handle)
    except OSError:
        sys.exit("Error reading input file.")

main()
