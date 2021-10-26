clear

rm -f test-out/*.gif

echo "=== These should cause two errors ==="
python3 gifenc.py -w0 test-in/empty.data test-out/empty.gif
python3 gifenc.py -w1 test-in/empty.data test-out/empty.gif
echo

rm -f test-out/empty.gif

echo "=== Encoding ==="
python3 gifenc.py -w10        test-in/blank100px.data test-out/blank100px.gif
echo "blank1mpx:"
python3 gifenc.py -w1000 -v   test-in/blank1mpx.data  test-out/blank1mpx.gif
echo "noise1bit:"
python3 gifenc.py -w1000 -v   test-in/noise1bit.data  test-out/noise1bit.gif
python3 gifenc.py -w202       test-in/triangle.data   test-out/triangle.gif
python3 gifenc.py -w320       test-in/wolf1bit.data   test-out/wolf1bit.gif
python3 gifenc.py -w320       test-in/wolf2bit.data   test-out/wolf2bit.gif
python3 gifenc.py -w320       test-in/wolf3bit.data   test-out/wolf3bit.gif
python3 gifenc.py -w320       test-in/wolf4bit.data   test-out/wolf4bit.gif
python3 gifenc.py -w320       test-in/wolf5bit.data   test-out/wolf5bit.gif
python3 gifenc.py -w320       test-in/wolf6bit.data   test-out/wolf6bit.gif
python3 gifenc.py -w320       test-in/wolf7bit.data   test-out/wolf7bit.gif
echo "wolf8:"
python3 gifenc.py -w320 -v    test-in/wolf8bit.data   test-out/wolf8bit.gif
echo "wolf8-nodictreset:"
python3 gifenc.py -w320 -r -v test-in/wolf8bit.data   test-out/wolf8bit-nodictreset.gif
echo "doom:"
python3 gifenc.py -w320 -v    test-in/doom.data       test-out/doom.gif
echo

echo "=== Source GIFs ==="
ls -lSr test-in/*.gif
echo

echo "=== Target GIFs (note: also verify them manually) ==="
ls -lSr test-out/*.gif
echo
