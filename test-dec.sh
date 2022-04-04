clear

rm -f test-out/*.data

echo "=== These should cause two errors ==="
python3 gifdec.py test-in/wolf8.gif  test-in/wolf8.gif
python3 gifdec.py test-in/empty.data test-out/empty.data
echo

echo "=== Decoding ==="
python3 gifdec.py    test-in/blank100px.gif    test-out/blank100px.data
python3 gifdec.py -v test-in/blank1mpx.gif     test-out/blank1mpx.data
python3 gifdec.py -v test-in/noise1bit.gif     test-out/noise1bit.data
python3 gifdec.py    test-in/triangle.gif      test-out/triangle.data
python3 gifdec.py    test-in/wolf1bit.gif      test-out/wolf1bit.data
python3 gifdec.py    test-in/wolf2bit.gif      test-out/wolf2bit.data
python3 gifdec.py    test-in/wolf3bit.gif      test-out/wolf3bit.data
python3 gifdec.py    test-in/wolf4bit.gif      test-out/wolf4bit.data
python3 gifdec.py    test-in/wolf5bit.gif      test-out/wolf5bit.data
python3 gifdec.py    test-in/wolf6bit.gif      test-out/wolf6bit.data
python3 gifdec.py    test-in/wolf7bit.gif      test-out/wolf7bit.data
python3 gifdec.py    test-in/wolf8bit.gif      test-out/wolf8bit.data
python3 gifdec.py    test-in/wolf8bit-lace.gif test-out/wolf8bit-lace.data
python3 gifdec.py    test-in/doom.gif          test-out/doom.data
python3 gifdec.py    test-in/anim.gif          test-out/anim.data
echo

echo "=== Verifying ==="
diff -q test-in/blank100px.data test-out/blank100px.data
diff -q test-in/blank1mpx.data  test-out/blank1mpx.data
diff -q test-in/noise1bit.data  test-out/noise1bit.data
diff -q test-in/triangle.data   test-out/triangle.data
diff -q test-in/wolf1bit.data   test-out/wolf1bit.data
diff -q test-in/wolf2bit.data   test-out/wolf2bit.data
diff -q test-in/wolf3bit.data   test-out/wolf3bit.data
diff -q test-in/wolf4bit.data   test-out/wolf4bit.data
diff -q test-in/wolf5bit.data   test-out/wolf5bit.data
diff -q test-in/wolf6bit.data   test-out/wolf6bit.data
diff -q test-in/wolf7bit.data   test-out/wolf7bit.data
diff -q test-in/wolf8bit.data   test-out/wolf8bit.data
diff -q test-in/wolf8bit.data   test-out/wolf8bit-lace.data
diff -q test-in/doom.data       test-out/doom.data
diff -q test-in/anim.data       test-out/anim.data
echo
