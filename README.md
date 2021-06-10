# pygif
GIF decoder/encoder in pure Python.

## Features
Decoder:
* supports interlaced images
* only extracts the first image from a file
* uses a lot of RAM

Encoder:
* doesn't support interlaced images
* always one image per file
* uses a lot of RAM

## Help text
```
usage: gif.py [-h] [-o {d,e,a}] [-w WIDTH] [-r] [-v] input_file output_file

Decode/encode a GIF file into/from raw RGB data (bytes: RGBRGB...; order of pixels: first right,
then down; file extension '.data' in GIMP).

positional arguments:
  input_file            File to read.
  output_file           File to write.

optional arguments:
  -h, --help            show this help message and exit
  -o {d,e,a}, --operation {d,e,a}
                        What to do (d=decode, e=encode, a=autodetect; default=a).
  -w WIDTH, --width WIDTH
                        Width of input file in pixels (encoding only).
  -r, --no-dict-reset   When encoding, don't reset the LZW dictionary when it fills up. May
                        compress highly repetitive images better.
  -v, --verbose         Print more info.
```
