clear

rm -f test-out/*.gif

echo "=== These should cause two errors ==="
python3 gifenc.py -w0 test-in/empty.data test-out/empty.gif
python3 gifenc.py -w1 test-in/empty.data test-out/empty.gif
echo

echo "=== Encoding ==="
python3 gifenc.py -w10 test-in/100px.data test-out/100px.gif
python3 gifenc.py -w202 test-in/triangle.data test-out/triangle.gif
python3 gifenc.py -w320 test-in/wolf1.data test-out/wolf1.gif
python3 gifenc.py -w320 test-in/wolf2.data test-out/wolf2.gif
python3 gifenc.py -w320 test-in/wolf3.data test-out/wolf3.gif
python3 gifenc.py -w320 test-in/wolf4.data test-out/wolf4.gif
python3 gifenc.py -w320 test-in/wolf5.data test-out/wolf5.gif
python3 gifenc.py -w320 test-in/wolf6.data test-out/wolf6.gif
python3 gifenc.py -w320 test-in/wolf7.data test-out/wolf7.gif
echo "wolf8:"
python3 gifenc.py -w320 -v test-in/wolf8.data test-out/wolf8.gif
echo "wolf8-nodictreset:"
python3 gifenc.py -w320 -r -v test-in/wolf8.data test-out/wolf8-nodictreset.gif
echo "doom:"
python3 gifenc.py -w320 -v test-in/doom.data test-out/doom.gif
echo

echo "=== Source GIFs ==="
ls -lSr test-in/*.gif
echo

echo "=== Target GIFs (note: also verify them manually) ==="
ls -lSr test-out/*.gif
echo
