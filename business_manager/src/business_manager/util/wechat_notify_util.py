# -*- coding:utf-8 -*-

KEY_TEMPLATE = "apply_{promise_repay_time}_{apply_id}"


def gen_key(promise_repay_time, apply_id):
    time = promise_repay_time.strftime("%Y-%m-%d-%H-%M")
    key = KEY_TEMPLATE.format(promise_repay_time=time, apply_id=str(apply_id))
    return key
