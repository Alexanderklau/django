# -*- coding: utf-8 -*-
from django.conf import settings
from django.shortcuts import render_to_response, get_object_or_404
from django.db.models import Q
from django.template import RequestContext,Template
from django.http import HttpResponse,HttpResponseRedirect

import json
from business_manager.order.models import *
from business_manager.util.tkdate import *

#for debug
from django.db import connection

class DataProvider():
    ''' 给DataTable提供数据的通用接口
        子类需要实现4个接口：
            object_filter() 获取数据的接口，一般从db中读出object_list，并根据request中的要求过滤（时间范围，人群，订单完成与否等等）
            get_columns() 返回datatables的 列名称， 返回list
            get_query() 数据过滤，返回搜索的查询条件，比如第一列是搜索那个字段，是完全匹配还是部分匹配，返回list
            fill_data() 数据展现，是把query_set 填充到最后的数据表中的过程，一般都是增加一些链接，做一些字符整理
        子类调用 get_datatable()就会返回需要的json数据
    '''
    def object_filter(self, request):
        return []

    def get_columns(self):
        return []

    def get_query(self):
        return []

    def fill_data(self, query_set):
        data_set = []
        for result in query_set:
            data = []
            data_set.append(data)
        return data_set

    def get_datatable(self, request):
        if request.method == 'GET':
            object_list = self.object_filter(request)
            if object_list:
                data = self._get_data(request, object_list)
                return HttpResponse(json.dumps(data))
        return HttpResponse(json.dumps({"recordsTotal": 0, "recordsFiltered": 0, "draw": "1", "data": []}))

    def get_records_count(self, query_set):
        return query_set.count()

    def _get_data(self, request, query_set):
        start = int(request.GET.get("start"))
        length = int(request.GET.get("length"))
        end = start + length
        search = request.GET.get("search[value]").encode('utf-8')
        reg = request.GET.get("search[regex]")
        seq = request.GET.get("draw")

        # 右上角的全文搜索
        if search != '':
            outputQ = None
            terms = search.split()
            for term in terms:
                output = None
                for query_cond in self.get_query():
                    kwargz = {query_cond : term}
                    output = output | Q(**kwargz) if output else Q(**kwargz)
                outputQ = outputQ & output if outputQ else output
            if not outputQ:
                outputQ = Q()
            query_set = query_set.filter(outputQ)

    #    # 单列搜索
    #    outputQ = None
    #    for col in range(0,cols):
    #        if request.GET.get('sSearch_{0}'.format(col), False) > '' and request.GET.get('bSearchable_{0}'.format(col), False) == 'true':
    #            kwargz = {columns[col]+"__icontains" : request.GET['sSearch_{0}'.format(col)]}
    #        outputQ = outputQ & Q(**kwargz) if outputQ else Q(**kwargz)
    #    if outputQ: query_set = query_set.filter(outputQ)

        # 排序
        asortingCols = []
        if query_set:
            query_fields = query_set[0].__dict__.keys()
        else:
            query_fields = []

        #只能 单个字段排序
        col_num = request.GET.get('order[0][column]', 0)
        col_num = int(col_num)
        for (i, column) in enumerate(self.get_columns()):
            if i != col_num:
                continue
            base = "columns[" + str(i) + "]"
            name = request.GET.get(base+"[name]")
            if not name:
                name = request.GET.get(base+"[data]")
            if name == '0':
                name = None
            if name == 'uid':
                name = 'id'
            searchable = request.GET.get(base+"[searchable]")
            orderable = request.GET.get(base+"[orderable]")
            value = request.GET.get(base+"[search][value]")
            value_reg = request.GET.get(base +"[search][regex]")
            order_way = request.GET.get("order[0][dir]")
            if order_way and name:
                if order_way == "asc":
                    sortedColName = name
                elif order_way == "desc":
                    sortedColName = "-" + name
                else:
                    continue
                if sortedColName and sortedColName != u'-' and name in query_fields:
                    asortingCols.append(sortedColName)
        query_set = query_set.order_by(*asortingCols)
        #if orderable:
        #    sortedColName = columns[sortedColID]
        #if iSortingCols:
        #    for sortedColIndex in range(0, iSortingCols):
        #        sortedColID = int(request.GET.get('iSortCol_'+str(sortedColIndex),0))
        #    if request.GET.get('bSortable_{0}'.format(sortedColID), 'false')  == 'true':
        #        sortedColName = columns[sortedColID]
        #    sortingDirection = request.GET.get('sSortDir_'+str(sortedColIndex), 'asc')
        #    if sortingDirection == 'desc':
        #        sortedColName = '-'+sortedColName
        #    asortingCols.append(sortedColName)
        #query_set = query_set.order_by(*asortingCols)
        total_records = filtered_records = self.get_records_count(query_set) #count how many records match the final criteria
        query_set = query_set[start:end] #get the slice
        table_data = self.fill_data(query_set)

        #total_records = filtered_records = len(table_data) #count how many records match the final criteria
        #filtered_records = len(table_data) #count how many records match the final criteria
        response_dict = {}
        # response_dict.update({'data':table_data[start:end]})
        response_dict.update({'data':table_data})
        response_dict.update({'url': request.build_absolute_uri(), 'recordsTotal': total_records, 'recordsFiltered': filtered_records, 'draw': seq})
        return response_dict

#def create_data_provider(factory):
#    provider = factory()
