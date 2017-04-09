# coding=utf-8
import requests
import json
# import round
import datetime
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from business_manager.python_common.log_client import CommonLog as Log
from business_manager.order.apply_models import ExtraApply, Apply
from business_manager.collection.models import RepaymentInfo, InstallmentDetailInfo
from business_manager.review import user_center_client

@csrf_exempt
def upload_info(request):
    if request.method == 'POST':
        # print request.POST.get('data')
        post_json_data = json.loads(request.POST.get('data'))
        apply_id = post_json_data.get('apply_id')
        template_id = post_json_data.get('template_id')
        json_data = json.dumps(post_json_data.get('json_data'))

        print apply_id, template_id, type(json_data)
        result = user_center_client.upload_order(str(apply_id), str(template_id), json_data)
        print result
        if result.code == 0:
            return HttpResponse(json.dumps({'code':0, 'msg':''}))

@csrf_exempt
def get_apply_info(request):
    if request.method == 'GET':
        apply_id = request.GET.get('apply_id')
        template_id = request.GET.get('template_id')
        apply_info = user_center_client.get_user_order(apply_id, template_id)
        return HttpResponse(apply_info.json_data)


@csrf_exempt
def upload_report(request):
    if request.method == 'GET':
        html =  '''
                <form enctype="multipart/form-data" method="post" action='/review/action/upload_report'>
                    <input type="file" name="file"/>
                    <input name="apply_id" value="15"/>
                    <input type="submit" />
                 </form>
                '''
        return HttpResponse(html)
    if request.method == 'POST':
        try:
            file_data = request.FILES['file']
            name = file_data.name
            file_type = name.split('.')[-1]
            files = {
                        'file':file_data.read()
                    }
            Log().info("upload_file ")
            res = requests.post(settings.IMAGE_SERVER_URL + "file", files=files, data={'type':file_type})
            Log().info("--- %s" % res)
            if res.content == 'fail':
                return HttpResponse('fail')
                # 返回错误json
            result = json.loads(res.content)
            #返回上传结果？？？？？
            resp = HttpResponse(json.dumps({'code':0, 'msg':'', 'url': result["url"]}))
            Log().info("upload_file success %s" % result["url"])
            return resp

        except Exception, e:
            return HttpResponse(json.dumps({"error" : u"文件上传失败"}))



def show_protocol_report(request, apply_id):
    if request.method == "GET":
        try:
            apply_obj = Apply.objects.get(pk=apply_id)
            repayment_id = apply_obj.repayment_id
            repay_obj = RepaymentInfo.objects.get(id=repayment_id)
            fee_info = detail_info = InstallmentDetailInfo.objects.filter(repayment=repay_obj)[1].repay_fee
            return render_to_response('review/server_protocol.html', {'fee':fee_info/100.00})
        except Exception as e:
            return HttpResponse(json.dumps({"error":"该订单还未通过审核"}))


def show_safeguard_report(request):
    if request.method == "GET":
        return render_to_response('review/safeguard.html')


def donwload_report(request, apply_id):
    if request.method == 'GET':
        try:
            # apply_id = request.GET.get('apply_id')
            print apply_id
            extra_apply = ExtraApply.objects.get(pk=apply_id)
            url = extra_apply.message_7
            return HttpResponse(json.dumps({'url':url}))
        except Exception as e:
            return HttpResponse('no apply object')

def show_repay_plant(request, apply_id):
    if request.method == 'GET':
        apply_obj = Apply.objects.get(pk=apply_id)
        repayment_id = apply_obj.repayment_id
        repay_obj = RepaymentInfo.objects.get(id=repayment_id)
        detail_info = InstallmentDetailInfo.objects.filter(repayment=repay_obj)
        info = [] 
        for detail_info_obj in detail_info:
            info.append((str(detail_info_obj.should_repay_time)[:10], detail_info_obj.should_repay_amount/100.00, detail_info_obj.installment_number),)
        return render_to_response('review/plant.html', {'result':info})



def show_backletter(request, apply_id):
    if request.method == 'GET':
        apply_obj = Apply.objects.get(pk=apply_id)
        name = apply_obj.create_by.name
        # 借款金额来源是Apply表还是Repayment表？？？
        print '-*'*30
        print apply_obj.amount
        money = _translate_number_to_chinese(apply_obj.amount/100)
        return render_to_response('review/backletter.html', {'id':'id', 'name':name, 'year':datetime.datetime.now().year, 
            'month':datetime.datetime.now().month, 'day':datetime.datetime.now().day, 'money':money})

# 阿拉伯数字转中文大写数字

CHINESE_NEGATIVE = '负'
CHINESE_ZERO = '零'
CHINESE_DIGITS = ['', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
CHINESE_UNITS = ['', '拾', '佰', '仟']
CHINESE_GROUP_UNITS = ['', '万', '亿', '兆']


def _enumerate_digits(number):
	"""
	:type number: int|long
	:rtype: collections.Iterable[int, int]
	"""
	position = 0
	while number > 0:
		digit = number % 10
		number //= 10
		yield position, digit
		position += 1


def _translate_number_to_chinese(number):
    """
    :type number: int|long
    :rtype: string
    """
    # 判断是否为整数
    # if not isinstance(number, int) and not isinstance(number, long):
        # raise ValueError('必须输入一个整数！！！')

    # 判断是否为零
    if number == 0:
        return CHINESE_ZERO
    words = []

    # 判断是否小于零
    if number < 0:
        words.append(CHINESE_NEGATIVE)
        number = -number

    # Begin core loop.
    # Version 0.2
    group_is_zero = True
    need_zero = False
    for position, digit in reversed(list(_enumerate_digits(number))):
        unit = position % len(CHINESE_UNITS)
        group = position //len(CHINESE_UNITS)

        if digit != 0:
            if need_zero:
                words.append(CHINESE_ZERO)

            words.append(CHINESE_DIGITS[digit])
            words.append(CHINESE_UNITS[unit])

        group_is_zero = group_is_zero and digit == 0

        if unit == 0:
            words.append(CHINESE_GROUP_UNITS[group])

        need_zero = (digit == 0 and (unit != 0 or group_is_zero))

        if unit == 0:
            group_is_zero = True

    return ''.join(words)
