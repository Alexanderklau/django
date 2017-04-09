from django.http import JsonResponse


class ImportResponse(object):

    success_code = 0
    failed_code = 1

    @classmethod
    def success(cls, data, msg='success'):
        return JsonResponse({
            'code': cls.success_code,
            'msg': msg,
            'data': data
        })

    @classmethod
    def failed(cls, data="", msg='failed'):
        return JsonResponse({
            'code': cls.failed_code,
            'msg': msg,
            'data': data
        })
