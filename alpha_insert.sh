#!/bin/bash
temp_file="temp.sort"
num_insertions=0
num_duplicates=0

# Copy contents of second file into first file
# ensuring no duplicates.
while read p; do
  if [ $(grep -w $p $2 | wc -l) -eq 0 ]; then
    echo $p >> $2
    num_insertions=$((num_insertions+1))
  else
    num_duplicates=$((num_duplicates+1))
  fi
done < $1

echo "NUMBER OF INSERTIONS: $num_insertions"
echo "NUMBER OF DUPLICATES: $num_duplicates"

sort $2 > $temp_file
cat $temp_file > $2
rm -f $temp_file

#end
