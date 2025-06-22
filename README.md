# pygif
GIF utilities in Python. Not to be confused with [the other pygif](https://github.com/robert-ancell/pygif).

*Note: This project has been moved to [Codeberg](https://codeberg.org/qalle/purepygif). This version will no longer be updated.*

Table of contents:
* [gifdec.py](#gifdecpy)
* [gifenc.py](#gifencpy)
* [gifstruct.py](#gifstructpy)
* [Other files](#other-files)

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
  output_file    Raw RGB image file to write. Format: 3 bytes (red, green,
                 blue) per pixel; order of pixels: first right, then down;
                 file extension '.data' in GIMP.

options:
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
  input_file           Raw RGB image file to read. Format: 3 bytes (red,
                       green, blue) per pixel; order of pixels: first right,
                       then down; file extension '.data' in GIMP. 256 unique
                       colors or less.
  width                Width of input_file in pixels.
  output_file          GIF file to write.

options:
  -h, --help           show this help message and exit
  -r, --no-dict-reset  Don't reset the LZW dictionary when it fills up. May
                       compress highly repetitive images better.
  -v, --verbose        Print more info.
```

## gifstruct.py
Print the high-level structure of a GIF file. Argument: file to read.

Example (a looping animated GIF with two frames and a comment):
```
$ python3 gifstruct.py test-in/anim.gif
Header:
    file offset: 0
    version: 89a
Logical Screen Descriptor:
    file offset: 6
    width: 29
    height: 9
    original color resolution in bits per RGB channel: 3
    pixel aspect ratio in 1/64ths: unknown
    has Global Color Table: yes
Global Color Table:
    file offset: 13
    colors: 4
    sorted: no
    background color index: 2
Extension:
    file offset: 25
    type: Application
    identifier: NETSCAPE
    authentication code: 2.0
Extension:
    file offset: 44
    type: Comment
    data: two frames with the words 'first' and 'second'
Extension:
    file offset: 94
    type: Graphic Control
    delay time in 1/100ths of a second: 100
    wait for user input: no
    transparent color index: none
    disposal method: unspecified
Image Descriptor:
    file offset: 102
    x position: 0
    y position: 0
    width: 29
    height: 9
    interlaced: no
    has Local Color Table: no
LZW data:
    file offset: 112
    palette bit depth: 2
    data size: 40
Extension:
    file offset: 155
    type: Graphic Control
    delay time in 1/100ths of a second: 100
    wait for user input: no
    transparent color index: 2
    disposal method: unspecified
Image Descriptor:
    file offset: 163
    x position: 0
    y position: 0
    width: 29
    height: 9
    interlaced: no
    has Local Color Table: no
LZW data:
    file offset: 173
    palette bit depth: 2
    data size: 46
Trailer:
    file offset: 222
```

## Other files
* `test-in/*.gif`: test images for the decoder; encoded with GIMP (some images are from *Wolfenstein 3D* and *Doom* by id Software)
* `test-out/raw-md5.txt`: MD5 hashes for correctly-decoded test images
* `test-dec.sh`: test the decoder using the test images
* `test-enc.sh`: test the encoder using the images created by `test-dec.sh`
