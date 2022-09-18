clear
rm -f test-out/*.data

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

echo "=== Verifying (should not print anything) ==="
cd test-out
md5sum -c --quiet raw-md5.txt
cd ..
echo
