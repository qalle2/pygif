clear

rm -f test-out/*.data
rm -f test-out/*.gif

echo "=== Corrupt a GIF and decode it ==="
python3 ~/git/file-corruptor/corruptor.py --count 8 test-in/wolf8.gif test-out/corrupt.gif
python3 gif.py -od -v test-out/corrupt.gif test-out/corrupt.data
echo
