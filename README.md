# pygif

## gifdec.py
A GIF decoder in pure Python. Notes:
* supports interlaced images
* only extracts the first image from a file
* uses a lot of RAM

```
usage: gifdec.py [-h] [-v] input_file output_file

Convert a GIF file into a raw RGB image file.

positional arguments:
  input_file     GIF file to read. Only the first image will be read.
  output_file    Raw RGB image file to write. Format: 3 bytes (red, green, blue) per pixel; order
                 of pixels: first right, then down; file extension '.data' in GIMP.

optional arguments:
  -h, --help     show this help message and exit
  -v, --verbose  Print more info.
```

## gifenc.py
A GIF encoder in pure Python. Notes:
* doesn't support interlaced images
* always one image per file
* uses a lot of RAM

```
usage: gifenc.py [-h] [-r] [-v] input_file width output_file

Convert a raw RGB image file into a GIF file.

positional arguments:
  input_file           Raw RGB image file to read. Format: 3 bytes (red, green, blue) per pixel;
                       order of pixels: first right, then down; file extension '.data' in GIMP.
                       256 unique colors or less.
  width                Width of input_file in pixels.
  output_file          GIF file to write.

optional arguments:
  -h, --help           show this help message and exit
  -r, --no-dict-reset  Don't reset the LZW dictionary when it fills up. May compress highly
                       repetitive images better.
  -v, --verbose        Print more info.
```
