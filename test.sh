clear

rm -f test-out/*.data
rm -f test-out/*.gif

echo "=== These should cause 4 errors ==="
python3 gif.py         test-in/wolf8.gif  test-in/wolf8.gif
python3 gif.py -od     test-in/wolf8.gif  test-in/wolf8.gif
python3 gif.py -od     test-in/empty.data test-out/empty.data
python3 gif.py -oe -w1 test-in/empty.data test-out/empty.gif
echo

echo "=== Decoding ==="
python3 gif.py     test-in/100px.gif      test-out/100px.data
python3 gif.py     test-in/triangle.gif   test-out/triangle.data
python3 gif.py     test-in/wolf1.gif      test-out/wolf1.data
python3 gif.py     test-in/wolf2.gif      test-out/wolf2.data
python3 gif.py     test-in/wolf3.gif      test-out/wolf3.data
python3 gif.py     test-in/wolf4.gif      test-out/wolf4.data
python3 gif.py     test-in/wolf5.gif      test-out/wolf5.data
python3 gif.py     test-in/wolf6.gif      test-out/wolf6.data
python3 gif.py     test-in/wolf7.gif      test-out/wolf7.data
python3 gif.py -v  test-in/wolf8.gif      test-out/wolf8.data
python3 gif.py     test-in/wolf8-lace.gif test-out/wolf8-lace.data
python3 gif.py -v  test-in/doom.gif       test-out/doom.data
python3 gif.py -v  test-in/photo.gif      test-out/photo.data
python3 gif.py -od test-in/anim.gif       test-out/anim.data
echo

echo "=== Verifying decoded files ==="
diff -q test-in/100px.data    test-out/100px.data
diff -q test-in/triangle.data test-out/triangle.data
diff -q test-in/wolf1.data    test-out/wolf1.data
diff -q test-in/wolf2.data    test-out/wolf2.data
diff -q test-in/wolf3.data    test-out/wolf3.data
diff -q test-in/wolf4.data    test-out/wolf4.data
diff -q test-in/wolf5.data    test-out/wolf5.data
diff -q test-in/wolf6.data    test-out/wolf6.data
diff -q test-in/wolf7.data    test-out/wolf7.data
diff -q test-in/wolf8.data    test-out/wolf8.data
diff -q test-in/wolf8.data    test-out/wolf8-lace.data
diff -q test-in/doom.data     test-out/doom.data
diff -q test-in/photo.data    test-out/photo.data
diff -q test-in/anim.data     test-out/anim.data
echo

echo "=== Encoding ==="
python3 gif.py -w10         test-in/100px.data    test-out/100px.gif
python3 gif.py -w202        test-in/triangle.data test-out/triangle.gif
python3 gif.py -w320        test-in/wolf1.data    test-out/wolf1.gif
python3 gif.py -w320        test-in/wolf2.data    test-out/wolf2.gif
python3 gif.py -w320        test-in/wolf3.data    test-out/wolf3.gif
python3 gif.py -w320        test-in/wolf4.data    test-out/wolf4.gif
python3 gif.py -w320        test-in/wolf5.data    test-out/wolf5.gif
python3 gif.py -w320        test-in/wolf6.data    test-out/wolf6.gif
python3 gif.py -w320        test-in/wolf7.data    test-out/wolf7.gif
python3 gif.py -w320 -v     test-in/wolf8.data    test-out/wolf8.gif
python3 gif.py -w320 -v     test-in/doom.data     test-out/doom.gif
python3 gif.py -oe -w526 -v test-in/photo.data    test-out/photo.gif
echo

echo "=== Source GIFs ==="
ls -lSr test-in/*.gif
echo

echo "=== Target GIFs (note: also verify them manually) ==="
ls -lSr test-out/*.gif
echo
