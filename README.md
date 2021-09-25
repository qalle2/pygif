# pygif
GIF decoder/encoder in pure Python.

## gifdec.py
The decoder. Notes:
* supports interlaced images
* only extracts the first image from a file
* uses a lot of RAM

```
usage: gifdec.py [-h] [-v] input_file output_file

Decode a GIF file into raw RGB data (bytes: RGBRGB...; order of pixels: first right, then down;
file extension '.data' in GIMP).

positional arguments:
  input_file     GIF file to read.
  output_file    Raw RGB data file to write.

optional arguments:
  -h, --help     show this help message and exit
  -v, --verbose  Print more info.
```

## gifenc.py
The encoder. Notes:
* doesn't support interlaced images
* always one image per file
* uses a lot of RAM

```
usage: gifenc.py [-h] -w WIDTH [-r] [-v] input_file output_file

Encode a GIF file from raw RGB data (bytes: RGBRGB...; order of pixels: first right, then down;
file extension '.data' in GIMP).

positional arguments:
  input_file            Raw RGB data file to read.
  output_file           GIF file to write.

optional arguments:
  -h, --help            show this help message and exit
  -w WIDTH, --width WIDTH
                        Width of input file in pixels. Required.
  -r, --no-dict-reset   Don't reset the LZW dictionary when it fills up. May compress highly
                        repetitive images better.
  -v, --verbose         Print more info.
```
