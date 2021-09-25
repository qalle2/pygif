clear

rm -f test-out/*.data

echo "=== These should cause two errors ==="
python3 gifdec.py test-in/wolf8.gif test-in/wolf8.gif
python3 gifdec.py test-in/empty.data test-out/empty.data
echo

echo "=== Decoding ==="
python3 gifdec.py test-in/100px.gif test-out/100px.data
python3 gifdec.py test-in/triangle.gif test-out/triangle.data
python3 gifdec.py test-in/wolf1.gif test-out/wolf1.data
python3 gifdec.py test-in/wolf2.gif test-out/wolf2.data
python3 gifdec.py test-in/wolf3.gif test-out/wolf3.data
python3 gifdec.py test-in/wolf4.gif test-out/wolf4.data
python3 gifdec.py test-in/wolf5.gif test-out/wolf5.data
python3 gifdec.py test-in/wolf6.gif test-out/wolf6.data
python3 gifdec.py test-in/wolf7.gif test-out/wolf7.data
echo "wolf8:"
python3 gifdec.py -v test-in/wolf8.gif test-out/wolf8.data
python3 gifdec.py test-in/wolf8-lace.gif test-out/wolf8-lace.data
echo "doom:"
python3 gifdec.py -v test-in/doom.gif test-out/doom.data
python3 gifdec.py test-in/anim.gif test-out/anim.data
echo

echo "=== Verifying ==="
diff -q test-in/100px.data test-out/100px.data
diff -q test-in/triangle.data test-out/triangle.data
diff -q test-in/wolf1.data test-out/wolf1.data
diff -q test-in/wolf2.data test-out/wolf2.data
diff -q test-in/wolf3.data test-out/wolf3.data
diff -q test-in/wolf4.data test-out/wolf4.data
diff -q test-in/wolf5.data test-out/wolf5.data
diff -q test-in/wolf6.data test-out/wolf6.data
diff -q test-in/wolf7.data test-out/wolf7.data
diff -q test-in/wolf8.data test-out/wolf8.data
diff -q test-in/wolf8.data test-out/wolf8-lace.data
diff -q test-in/doom.data test-out/doom.data
diff -q test-in/anim.data test-out/anim.data
echo
