#!/bin/bash

git submodule update --init --recursive

grep path .gitmodules | awk '{print $3}' > ./tmp_submodule_dirs

while read line
do
    echo $line
    cd ./$line 
    git pull origin master
    git checkout saas && git pull origin saas
    f_list=`find . -name "*.thrift"`
    echo $f_list
    for f in $f_list
    do
        o_path=${f%/*}
        echo $f $o_path
        thrift --gen py -o $o_path $f
    done
    cd -
done < ./tmp_submodule_dirs
rm -f ./tmp_submodule_dirs
