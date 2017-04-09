# -*- coding:utf-8 -*-

from datetime import datetime
from django.db.models.query import QuerySet

from django.shortcuts import render

from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import APIException

from business_manager.import_data.services import CuteViewSet
from business_manager.import_data.services import get_request_data, update_attr
from business_manager.import_data.models import TEMP
from business_manager.import_data.models import USING, ACTIVE
from business_manager.strategy.models import Strategy2
from business_manager.strategy.serializers import Strategy2Serializer, Strategy2ListSerializer

from business_manager.util.common_response import ImportResponse
from business_manager.review import risk_client
from business_manager.employee.models import get_employee_platform


class Strategy2ViewSet(CuteViewSet):

    serializer_class = Strategy2Serializer
    # serializer_class_retrieve = ImportModuleRetrieveSerializer
    serializer_class_list = Strategy2ListSerializer
    queryset = Strategy2.objects.all()

    def get_queryset(self):
        """queryset 状态 < 0 的不返回"""
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # Ensure queryset is re-evaluated on each request.
            queryset = queryset.all()

        if self.platform:
            queryset = queryset.filter(status__gte=0, belong_platform__in = self.platform).order_by('-update_at')
        else:
            queryset = queryset.filter(status__gte=0).order_by('-update_at')

        return queryset

    def destroy(self, request, *args, **kwargs):
        """删除: 将 instance 状态 修改为 -1 (< 0 表示用户不可见)"""
        instance = self.get_object()
        if instance.status in [USING]:
            # return Response(status=status.HTTP_204_NO_CONTENT,data=0)
            data = dict(
                code=1,
                msg=u'{} 贷款策略在使用中, 不能删除'.format(instance.name),
                data={},
            )
            return Response(data=data)

        return super(Strategy2ViewSet, self).destroy(request, *args, **kwargs)

    @detail_route(methods=['post'])
    def post(self, request, pk=None):
        """"""
        print 'in method'
        print pk
        instance = self.get_object()
        print instance
        print type(instance)

        data = get_request_data(request, True)
        method = data.get('method')
        print data
        print method
        # return 
        if data.get('data'):
            amount_ceil = data['data'].get('amount_ceil', 1)
        if isinstance(amount_ceil, (int, long)) and amount_ceil > 2147483647:
            return Response(
                data=dict(
                        code=500,
                        msg=u"请确保贷款金额上限小于或者等于 21474836.47元",
                        data=""
                    )
                )
        if method == 'delete':
            # update_attr(instance, dict(status=-1))
            # instance.save()
            # return Response(status=status.HTTP_204_NO_CONTENT)
            return self.destroy(request)#, *args, **kwargs)
        if method == 'update':
            print 'in update'
            return self.update(request)#, *args, **kwargs)
        data = dict(
            code=0,
            msg='',
            data={},
        )
        return Response(data)


    @detail_route(methods=['post'])
    def active(self, request, pk=None):
        """策略是否启用

        """
        instance = self.get_object()
        status = instance.status
        if status in [USING]:
            status_msg = u'正在使用中'
            msg = u'{}, {} 不能修改或删除.'.format(instance.name, status_msg)
            raise APIException(msg)

        data = get_request_data(request)
        print data
        active = int(data.get('active', -1))
        print active
        print type(active)
        if active == 1:
            status = 5
            is_active = 1
        elif active == 0:
            status = 0
            is_active = 0
        else:
            msg = u'error: active: {} not in [0, 1]'.format(active)
            code = 500
            data = dict(
                code=code,
                msg=msg,
                data=dict(status=instance.status),
            )
            return Response(data)

        print status
        update_attr(instance, dict(status=status, active=is_active), partial=False)
        instance.save()

        data = dict(
            code=0,
            msg='',
            data=dict(status=instance.status),
        )
        return Response(data)

    @list_route(methods=['post'])
    def trial(self, request):
        """为贷款试算, 保存的 临时 策略"""
        print 'in trail method'
        data = get_request_data(request)
        name = data.get('name')
        name += str(datetime.now())
        amount_ceil = data.get('amount_ceil', 1)
        if isinstance(amount_ceil, (int, long)) and amount_ceil > 2147483647:
            return Response(
                data=dict(
                        code=500,
                        msg=u"请确保贷款金额上限小于或者等于 21474836.47元",
                        data=""
                    )
                )
        update_data = dict(name=name)
        valid_data = dict(status=TEMP)
        return self.create(request, valid_data=valid_data, update_data=update_data)


        # data = get_request_data(request, True)
        # method = data.get('method')
        # print data
        # print method

        # data = dict(
            # code=0,
            # msg='',
            # data=dict(id=1),
        # )
        # return Response(data)



def repay_calculation(request):
    if request.method != 'GET':
        return ImportResponse.failed(msg="wrong method")
    print request.GET
    strategy_id = request.GET.get('strategy_id')
    repay_amount = request.GET.get('repay_amount')
    if not any([strategy_id, repay_amount]):
        return ImportResponse.failed(msg="wrong parameters")
    res = risk_client.loan_trial(int(repay_amount), int(strategy_id))
    # import pdb; pdb.set_trace()
    # print res
    if not res:
        return ImportResponse.failed(msg="risk management server error")
    if res.result_code != 0:
        if res.result_code == -2:
            return ImportResponse.failed(msg=u"大人金额为0,试算不能啊~")
        return ImportResponse.failed(msg=res.error_msg)
    data = []
    for item in res.data:
        data.append(
            {
                "installment_number": item.installment_number,
                "should_repay_time": item.should_repay_time,
                "should_repay_amount": item.should_repay_amount,
                "repay_interest": item.repay_interest,
                "repay_principle": item.repay_principle,
                "rest_repay_money": item.rest_repay_money,
                "repay_fee": item.repay_fee,
            }
        )
    return ImportResponse.success(data=data)
