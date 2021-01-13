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
usage: gif.py [-h] [-o {d,e}] [-w WIDTH] [-l] input_file output_file

Decode/encode a GIF file into/from raw RGB data (bytes: RGBRGB...; order of
pixels: first right, then down; file extension '.data' in GIMP).

positional arguments:
  input_file            File to read.
  output_file           File to write.

optional arguments:
  -h, --help            show this help message and exit
  -o {d,e}, --operation {d,e}
                        What to do (d=decode, e=encode). Required.
  -w WIDTH, --width WIDTH
                        Width of input file in pixels (encoding only).
  -l, --log             Print decode/encode log.
```

