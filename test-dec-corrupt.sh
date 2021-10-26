clear

rm -f test-out/*.data
rm -f test-out/*.gif

echo "=== Corrupt GIFs and try to decode them ==="
echo
for ((i = 0; i < 4; i++))
do
    python3 ~/git/file-corruptor/corruptor.py --count 8 test-in/wolf8bit.gif test-out/corrupt$i.gif
    echo "corrupt$i.gif:"
    python3 gifdec.py -v test-out/corrupt$i.gif test-out/corrupt$i.data
done
echo
