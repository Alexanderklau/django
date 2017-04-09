# -*- coding: utf-8 -*-
from pyExcelerator import *
import xlrd
import sys
import re


#def import_from_file(filename, i):
#    wb = xlrd.open_workbook(filename)  #打开文件
#    sh = wb.sheet_by_index(i) #获得工作表的方法1
#    #row_count=sh.nrows #获得行数
#    #col_count=sh.ncols  #获得列数
#    #cellA1Value = sh.cell_value(0, 1) #获得单元格数据
#    return sh

def get_name_from_file(filename):
    wb = xlrd.open_workbook(filename)  #打开文件
    sh = wb.sheet_by_index(0) #获得客户信息
    name_list = []
    for i in range(1, sh.nrows):
        name_list.append((sh.cell_value(i, 0), str(int(sh.cell_value(i, 1))))) #添加身份证号
    return name_list

def compare_payed(file1, file2):
    name_list1 = get_name_from_file(file1)
    #print name_list1
    #print "payed, ", len(name_list1)
    name_list2 = get_name_from_file(file2)
    #print name_list2
    #print "payed, ", len(name_list2)
    payed_list = list(set(name_list1).difference(set(name_list2)))
    print "实际回款客户, ", len(payed_list)
    #print_list(payed_list)
    return payed_list

def print_list(name_list):
    for i in name_list:
        print i[0], i[1]

def compare_missed(filename, payed_list):
    wb = xlrd.open_workbook(filename)  #打开文件
    sh = wb.sheet_by_index(2) #获得回款情况

    name_list = []
    for i in range(1, sh.nrows):
       name_list.append((sh.cell_value(i, 0), str(int(sh.cell_value(i, 2)))))
       # name_list.append((sh.cell_value(i, 0), str(int(sh.cell_value(i, 1))))) #添加身份证号
    print "回款, ", len(name_list)
    #print_list(name_list)
    missed_list = list(set(payed_list).difference(set(name_list)))
    print "缺失, ", len(missed_list)
    print_list(missed_list)
    return missed_list

if __name__ == "__main__":
    #filenames = settings.IMPORT_FILE
    file1 = sys.argv[1]#"融数通催收数据导出-6.16.xlsx"
    file2 = sys.argv[2]#"融数通催收数据导出-6.17.xlsx"
    #file1 = "融数通催收数据导出-6.17.xlsx"
    #file2 = "融数通催收数据导出-6.18.xlsx"
    print file2
    payed_list = compare_payed(file1, file2)
    missed_list = compare_missed(file2, payed_list)
    #for xls_file in filenames:
    #    print "import xls_file", xls_file
    #    import_from_file(xls_file)
