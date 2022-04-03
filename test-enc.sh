clear

rm -f test-out/*.gif

echo "=== These should cause two errors ==="
python3 gifenc.py test-in/empty.data 0 test-out/empty.gif
python3 gifenc.py test-in/empty.data 1 test-out/empty.gif
echo

rm -f test-out/empty.gif

echo "=== Encoding ==="
python3 gifenc.py    test-in/blank100px.data   10 test-out/blank100px.gif
python3 gifenc.py -v test-in/blank1mpx.data  1000 test-out/blank1mpx.gif
python3 gifenc.py -v test-in/noise1bit.data   500 test-out/noise1bit.gif
python3 gifenc.py    test-in/triangle.data    202 test-out/triangle.gif
python3 gifenc.py    test-in/wolf1bit.data    320 test-out/wolf1bit.gif
python3 gifenc.py    test-in/wolf2bit.data    320 test-out/wolf2bit.gif
python3 gifenc.py    test-in/wolf3bit.data    320 test-out/wolf3bit.gif
python3 gifenc.py    test-in/wolf4bit.data    320 test-out/wolf4bit.gif
python3 gifenc.py    test-in/wolf5bit.data    320 test-out/wolf5bit.gif
python3 gifenc.py    test-in/wolf6bit.data    320 test-out/wolf6bit.gif
python3 gifenc.py    test-in/wolf7bit.data    320 test-out/wolf7bit.gif
python3 gifenc.py    test-in/wolf8bit.data    320 test-out/wolf8bit.gif
python3 gifenc.py -r test-in/wolf8bit.data    320 test-out/wolf8bit-nodictreset.gif
python3 gifenc.py    test-in/doom.data        320 test-out/doom.gif
echo

echo "=== Source GIFs ==="
ls -lSr test-in/*.gif
echo

echo "=== Target GIFs (note: also verify them manually) ==="
ls -lSr test-out/*.gif
echo
