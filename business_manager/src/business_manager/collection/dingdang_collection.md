## 贷后信息导入接口说明

### 接口功能
* 接入其他第三方提供催收模块相关的信息接入我们平台的数据库，创建催收订单提供贷后服务

### 信息导入接口url

* 提交方式： POST
* URL:  /collection/import_collection_info
* "Content-type": "application/json"

### 请求参数
字段 | 含义 | 值类型 | 是否必填 | 备注
---|---|---|---|---
all_collection_data_length | 数据总量 | str | N |(方便统计，校验)
actual_collection_data | 导入的催收数据 | List | Y
user_info | 用户信息 | str | Y
user_info/channel | 用户渠道来源 | str | Y
user_info/user_info/name | 用户姓名 | str | Y
user_info/id_no | 用户身份证 | str | Y
user_info/phone_no | 用户电话 | str | Y
user_info/work_address | 工作地址 | str | Y
user_info/work_name | 公司名称 | str | Y|
user_info/home_number | 单位电话 | str | Y|
user_info/home_address | 家庭地址 | str | Y
user_info/register_time | 注册时间 | str | Y |  2016-01-01 10:00:00格式
user_info/contact_list | 用户亲密联系人(0到多个) | List | Y
user_info/contact_list/relationship | 亲密联系人关系 | str | N
user_info/contact_list/name | 亲密联系人 | str | Y
user_info/contact_list/phone_no | 亲密联系人联系电话 | str | Y
repayment_info/repayment_id | 借贷id | str | Y |
repayment_info/amount | 借贷金额 | str | Y
repayment_info/apply_time | 申请时间 | date time | Y
repayment_info/pay_time | 放款时间 | date time | Y
strategy_id | 用户当前贷款策略ID | str | Y | 用于计算逾期天数和计算何时开始逾期（由于这里不考虑这个问题 都写成100即可）
card_info/card_number | 银行卡号 | str | Y |
card_info/card_type | 银行卡号 | str | Y |
card_info/bank_type | 银行类型 | str | Y |
user_info/gender | 用户性别 | str | N
user_info/marry_status | 用户婚姻状况 | str | N
user_info/type | 用户类型 | str | N
user_info/qq | 用户qq | str | N

ison格式约束上 可以选填的 可以没有这个字段 比如 info/user_info/marry_status  但是如果有了这个key 后面的value不能为空字符串

示例:


```
{

    "all_collection_data_length": "1",
    "actual_collection_data": [
        {
            "user_info": {
                "name": "name123",
                "phone_no": "13921341234",
                "id_no": "430202198711032018",
                "channel" : "叮当钱包",
                "register_time" : "2013-10-10 23:40:00"
                "home_address" : "xxxx",
                "work_address" : "xxxx",
                "wrok_name" : "xxxx",
                "work_number" : "010-1231231",
                "mariage" : 1,
                "email": "xxxx@xxx.com",
                "contact_list": [
                    {
                        "name": "某某",
                        "relationship": "",
                        "phone_no": "13880296423"
                    },
                    {
                        "name": "某某2",
                        "relationship": "父母",  #这里给我一个列表
                        "phone_no": "13423562345"
                    }
                ]
            },
            "card_info" : {
                "card_number" : "232131241421321321",
                "card_type" : 3,  #这里都写3
                "bank_type" : "BCC", #这里给我一个列表
                "phone_no" : "13412341234"
            },
            "repayment_info": {
                "repayment_id": "dingdang_12345", # 唯一编号 麻烦用dingdang_工单号
                "amount": 10000,# 金额  10000分
                "repay_amount" : 11000, #应还金额
                "rest_amount" : 5000, #结清金额
                "installment_count" : 12, # 12期
                "apply_time": "2013-10-10 23:40:00",#申请时间
                "pay_time": "2013-10-10 23:40:00", #打款时间
                "installment_info" : [{
                    "installment_id" : 1,
                    "installment_status" : 2, #都写成2
                    "should_pay_amount" : 11000,
                    "overdue_amount" : 1000,
                    "exact_pay_amount" : 0,# 都写成0好了
                    "overdue_days": 4 ,    # 逾期天数
                },{
                    "installment_id" : 2,
                    "installment_status" : 2, #都写成2
                    "should_pay_amount" : 11000,
                    "overdue_amount" : 1000,
                    "exact_pay_amount" : 0,# 都写成0好了
                    "overdue_days": 4 ,
                }
                ]
            },
            "strategy_id": 11
        }
    ]
}

```

### 信息更新接口url

* 提交方式： POST
* URL:  /collection/update_collection_info
* "Content-type": "application/json"

### 请求参数
字段 | 含义 | 值类型 | 是否必填 | 备注
---|---|---|---|---

### 示例:
更新已经还款的贷款条目 （这里暂时约定只能还清一笔贷款，不能部分还款）

```
{
    "all_collection_data_length": "1",
    "actual_collection_data": [
        {
            "user_info": {
                "name": "name123",
                "phone_no": "13921341234",
                "id_no": "430202198711032018",
            },
            "repayment_info": {
                "repayment_id": "dingdang_12345",
                "amount": "10000",   #还款金额
                "apply_time": "2013-10-10 23:40:00",
                "pay_time": "2013-10-10 23:40:00"
            },
        }
    ]
}
```

### 返回结果

字段| 说明 | 备注
----|------|-----
error_list | 如果不成功,导入出错的催收单号List
error_list/err_message | 具体出错信息 |  有可能是个json
error_list/err_code | 错误码 | 可能没有有

示例:

成功示例
```
    {"error_list": [], "fail_num": 0, "success_num": 1}
```
失败示例
```
{
    "error_list":
    [{
        "error_no": 21003,
        "error_detail": "12,13921341234多个重复用户字段主键重复，无法导入",
        "error_msg": "主键重复"
    }],
    "fail_num": 1,
    "success_num": 0
}

```

### 错误码列表
该接口错误码范围都在21000-22000之间

错误码|说明|备注
---|---|---
 0 | 成功 |
 21000| 字段缺失 |
 21001| 字段不能为空 |
 21002| 字段不合法|
 21003| 主键重复|
 21004| json格式错误|
 21005| db错误|
 21100| 其他内部错误|


