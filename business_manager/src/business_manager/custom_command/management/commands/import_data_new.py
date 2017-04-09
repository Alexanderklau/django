# -*- coding:utf-8 -*-
import json
import os
import time
from multiprocessing import Process, Pool
from hashlib import md5

from django.core.management.base import BaseCommand

from business_manager.collection.batch_import import import_collection_info
from business_manager.collection.batch_import import import_callrecords_info
from business_manager.collection.batch_import import update_collection_info
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.custom_command.management.commands import dispatch_scala
from business_manager.custom_command.management.commands import update_apply

from datetime import datetime


# FILE_PATH = r'/home/dengzhehao/data/'
# BACK_UP_PATH_BASE = r'/home/dengzhehao/backup/'

FILE_PATH = r'/home/dev/dev/data/'
BACK_UP_PATH_BASE = r'/home/dev/dev/bak/'


class Command(BaseCommand):

    record_md5_file = FILE_PATH + 'record_md5.txt'
    file_type_list = ('YQ', 'HK', 'TXL')
    check_file_list = []
    process_list = []
    md5_list = set()

    def handle(self, *args, **options):
        start = datetime.now()
        
        file_start = datetime.now()
        self.load_file_md5()
        file_end = datetime.now()
        print 'load file cost: %s' % str(file_end - file_start)

        import_data_start = datetime.now()
        if not args:
            for file_type in self.file_type_list:
                self.check_file_list = (file_type, )
                self.process_list = []
                self.import_check()
            else:
                print('import file_type: {}'.format(self.check_file_list))
        else:
            self.check_file_list = map(lambda i: i.upper(), args)
            self.import_check()
            # do import yq and import txl
        import_data_end = datetime.now()
        print 'import data cost: %s' % str(import_data_end - import_data_start)

        # 开始自动分单
        self.start_dispatch()
        # # 处理期款
        update_apply_start = datetime.now()
        update_apply.Command().handle()
        update_apply_end = datetime.now()
        print 'import data cost: %s' % str(update_apply_end - update_apply_start)

        end = datetime.now()
        print 'total cost: %s' % str(end - start)

    def start_dispatch(self):
        try:
            print('start dispatch m1')
            dispatch_scala.Command().handle('m1', '23,24,34,41', '50,50,50,50')
            print('dispatch m1 success')
            print('start dispatch m2')
            dispatch_scala.Command().handle('m2', '22,33', '50,50')
            print('dispatch m2 success')
            print('start dispatch m3')
            dispatch_scala.Command().handle('m3')
            print('dispatch m3 success')
        except Exception as e:
            print('dispatch error: %s' % e)

    def read_file(self, filename):
        with open(filename, 'r') as f:
            content = f.read()
        try:
            content = json.loads(content)
            return content
        except:
            raise FileNotCompleteException(filename)

    def import_dispatch(self, content, filename):
        if 'TXL' in filename:
            self.move_to_backup(filename, 'TXL')
        elif 'HK' in filename:
            self.import_hk(content)
            self.record_file_md5(filename)
            self.move_to_backup(filename, 'HK')
        elif 'YQ' in filename:
            self.import_data(content)
            self.record_file_md5(filename)
            self.move_to_backup(filename, 'YQ')

    def import_data(self, content):
        try:
            data = json.dumps(content)
            data_dic = json.loads(data)['actual_collection_data']
            data_len = len(data_dic)
            pool = Pool(5)
            range_num = 150
            for i in range(data_len / range_num + 1):
                print i
                new_data = {
                        "actual_collection_data": data_dic[i * range_num: (i + 1) * range_num],
                        "all_collection_data_length": range_num,
                }
                new_data = json.dumps(new_data)
                ret = pool.apply_async(import_collection_info, args=(FakeReq(new_data, 'POST'),))

            pool.close()
            pool.join()
            print('import result: ', ret)
        except Exception as e:
            print('import yq error: ', e)

    def import_hk(self, content):
        try:
            data = json.dumps(content)
            ret = update_collection_info(FakeReq(data, 'POST'))
            print('import hk: ', ret)
        except Exception as e:
            print('import hk error: ', e)

    def import_txl(self, content):
        try:
            data = json.dumps(content)
            ret = import_callrecords_info(FakeReq(data, 'POST'))
            print('import txl: ', ret)
        except Exception as e:
            print('import txl error: ', e)

    def import_check(self):
        file_list = os.listdir(FILE_PATH)
        if not file_list:
            return
        file_list = self.filter_file(file_list)
        while file_list:
            file_ = file_list.pop(0)
            file_ = FILE_PATH + file_
            if self.check_file(file_):
                try:
                    content = self.read_file(file_)
                    # self.multi_import(content, file_)
                    self.import_dispatch(content, file_)
                except FileNotCompleteException as e:
                    Log().error('import file error: %s, error file: %s' % (e, file_))
                    print('import file error: %s, error file: %s' % (e, file_))
                    # not_complete_file = e.filename
                    # file_list.append(not_complete_file)
        # try:
            # map(lambda i: i.start(), self.process_list)
        # except Exception as e:
            # print('run error: ', e)
            # return
        # try:
            # map(lambda i: i.join(), self.process_list)
        # except Exception as e:
            # print('process join error:', e)
            # return
        print('import file complete')

    def multi_import(self, content, file_):
        pass
        # p = Process(target=self.import_dispatch, args=(content, file_))
        # self.process_list.append(p)

        # print 'Process will start.'
        # p.start()
        # p.join()
        # self.import_dispatch(content, file_)

    def filter_file(self, file_list):
        ret = []
        for f in file_list:
            for f_type in self.check_file_list:
                if f_type in f and not self.check_in_received_file(f):
                    ret.append(f)
        return ret

    def check_in_received_file(self, file_):
        print('check file: %s md5' % file_)
        file_md5 = calc_md5(FILE_PATH+file_)
        if file_md5 in self.md5_list:
            file_type = filter(lambda i: i in file_, self.file_type_list)
            move_file = file_type[0] if file_type else None
            if move_file:
                self.move_to_backup(FILE_PATH+file_, move_file)
            print('file: %s already imported' % file_)
            return True
        else:
            return False

    def check_file(self, file_):
        if not os.path.isfile(file_):
            return
        if 'HK' in file_:
            self.check_yq_complete()
        check_time = 0
        while True:
            check_time += 1
            file_size = self.get_file_size(file_)
            time.sleep(5)
            # if check_time > 30:
            #     return True
            if file_size == self.get_file_size(file_):
                return True

    def check_yq_complete(self):
        try:
            file_list = os.listdir(FILE_PATH)
        except Exception as e:
            print('read FILE_PATH: %s error: ' % FILE_PATH, e)
            return
        while True:
            yq_file = filter(lambda i: 'YQ' in i, file_list)
            if not yq_file:
                break
            print('import YQ data not complete! YQ file: %s' % yq_file)
            time.sleep(5)
            break

    def get_file_size(self, file_):
        with open(file_, 'r') as f:
            return len(f.read())

    def move_to_backup(self, file_, file_type):
        filename = file_.split('/')[-1]
        date = filename[:10] + '/'
        try:
            save_path = BACK_UP_PATH_BASE + date + file_type + '/'
            self.check_dir(save_path)
            print('move file: %s to %s' % (file_, save_path))
            os.rename(file_, save_path+filename)
        except Exception as e:
            print("move file error: %s" % e)
            Log().error("move file error: %s" % e)

    def check_dir(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    def record_file_md5(self, filename):
        file_md5 = calc_md5(filename)
        with open(self.record_md5_file, 'a+') as f:
            f.write('%s %s\n' % (file_md5, filename))

    def load_file_md5(self):
        with open(self.record_md5_file, 'r') as f:
            for line in f:
                self.md5_list.add(line.split()[0])
        print('self.md5_list: %s ' % self.md5_list)


class FakeReq:
    def __init__(self, body, method):
        self.body = body
        self.method = method


class FileNotCompleteException(BaseException):

    def __init__(self, filename):
        self.filename = filename


def calc_md5(file_):
    try:
        m = md5()
        with open(file_, 'rb') as f:
            m.update(f.read())
        return m.hexdigest()
    except Exception as e:
        print('calc file %s error %s ' % (file_, e))
        return ''
