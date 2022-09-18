# Run test-dec.sh first to create the source files for this script.

clear
rm -f test-out/*.gif

echo "=== Encoding ==="
python3 gifenc.py    test-out/blank100px.data   10 test-out/blank100px.gif
python3 gifenc.py -v test-out/blank1mpx.data  1000 test-out/blank1mpx.gif
python3 gifenc.py -v test-out/noise1bit.data   500 test-out/noise1bit.gif
python3 gifenc.py    test-out/triangle.data    202 test-out/triangle.gif
python3 gifenc.py    test-out/wolf1bit.data    320 test-out/wolf1bit.gif
python3 gifenc.py    test-out/wolf2bit.data    320 test-out/wolf2bit.gif
python3 gifenc.py    test-out/wolf3bit.data    320 test-out/wolf3bit.gif
python3 gifenc.py    test-out/wolf4bit.data    320 test-out/wolf4bit.gif
python3 gifenc.py    test-out/wolf5bit.data    320 test-out/wolf5bit.gif
python3 gifenc.py    test-out/wolf6bit.data    320 test-out/wolf6bit.gif
python3 gifenc.py    test-out/wolf7bit.data    320 test-out/wolf7bit.gif
python3 gifenc.py    test-out/wolf8bit.data    320 test-out/wolf8bit.gif
python3 gifenc.py -r test-out/wolf8bit.data    320 test-out/wolf8bit-nodictreset.gif
python3 gifenc.py    test-out/doom.data        320 test-out/doom.gif
echo

echo "=== Sizes of preexisting GIFs ==="
ls -lSr test-in/*.gif
echo

echo "=== Sizes of encoded GIFs (note: also verify them manually) ==="
ls -lSr test-out/*.gif
echo
