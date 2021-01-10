# pygif
GIF decoder/encoder in pure Python.

## Features

Decoder:
* supports interlaced images
* only extracts the first image from a file
* quite fast
* uses a lot of RAM

Encoder:
* doesn't support interlaced images
* always one image per file
* quite fast
* uses a lot of RAM

## Help text

```
Decodes a GIF file into raw RGB data or encodes raw RGB data into a GIF file.
(Bytes in raw RGB data: RGBRGB...; order of pixels: first right, then down;
file extension ".data" in GIMP.)

Arguments when decoding: SOURCE TARGET
    SOURCE = GIF file to read
    TARGET = raw RGB data file to write

Arguments when encoding: SOURCE WIDTH TARGET
    SOURCE = raw RGB data file to read
    WIDTH  = width of SOURCE in pixels
    TARGET = GIF file to write
```

