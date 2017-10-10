#!/bin/bash
temp_file="temp.sort";

# Copy contents of second file into first file
# ensuring no duplicates.
while read p; do
  if [ $(grep -w $p $2 | wc -l) -eq 0 ]; then
    echo $p >> $2
  fi
done < $1

sort $2 > $temp_file
cat $temp_file > $2
rm -f $temp_file

#end
