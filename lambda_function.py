import boto3
import time
import urllib
import json
import os
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    pInstanceId = event['instanceId']
    pInstanceName = event['instanceName']
    pInstanceType1 = event['instanceType1']
    pInstanceType2 = event['instanceType2']

    pCount = event['count']

    ec2 = boto3.client('ec2', region_name=os.environ['REGION'])
    
    #EC2状態取得
    response = ec2.describe_instances(
        Filters=[{'Name':'instance-id','Values':[pInstanceId]}]
    )
    #起動してなかったら起動する
    if response['Reservations'][0]['Instances'][0]["State"]["Name"] != "running":
        try:
            #1回目はm5a、2回目はm4で空いてるキャパシティを探す
            if pCount % 2 == 0:
                instanceType = pInstanceType1
            else:
                instanceType = pInstanceType2
            
            print(instanceType)
                
            #EC2インスタンスタイプ変更
            ec2.modify_instance_attribute(InstanceId=pInstanceId, Attribute='instanceType', Value=instanceType)
            #EC2起動
            ec2.start_instances(InstanceIds=[pInstanceId])
            print('started instances: ' + str(pInstanceId))
        except ClientError as e:
            #キャパシティエラー等
            print('start error ['+str(pInstanceId)+']:'+str(e.response['Error']['Code']))
            #一回目だけ通知
            if pCount == "1":
                post_slack(pInstanceName+'： retry ('+str(e.response['Error']['Code'])+')')

    #2分待つ
    time.sleep(120)

    #EC2状態再取得
    response = ec2.describe_instances(
        Filters=[{'Name':'instance-id','Values':[pInstanceId]}]
    )
    
    print('ec2: ' + str(response))

    #起動してなかったら再帰呼び出し    
    if response['Reservations'][0]['Instances'][0]["State"]["Name"] != "running":
        #強制終了モードなら再帰処理を実行しない
        if os.environ["FORCE_END"] != "1":
            # 引数
            input_event = {
                "instanceId": pInstanceId,
                "instanceName": pInstanceName,
                "instanceType1": pInstanceType1,
                "instanceType2": pInstanceType2,
                "count": int(pCount) + 1
            }
            Payload = json.dumps(input_event) # jsonシリアライズ
             
            # 呼び出し
            response = boto3.client('lambda').invoke(
                FunctionName=os.environ['CALL_FUNC'],
                InvocationType='Event',
                Payload=Payload
            )
        else:
            print(pInstanceName+pCount+'回目で強制終了')       

    #起動してたらslack通知
    else:
        post_slack(pInstanceName+'waked up ('+str(pCount)+'count success!)')

def post_slack(pText):

    # 設定
    SLACK_POST_URL = "https://hooks.slack.com"+os.environ['SLACK_URL']
    method = "POST"

    # メッセージの内容
    send_data = {
        "username":os.environ['SLACK_USER'],
        "text":pText,
        "icon_emoji":os.environ['ICON']
    }

    send_text = ("payload=" + json.dumps(send_data)).encode('utf-8')

    request = urllib.request.Request(
        SLACK_POST_URL,
        data=send_text,
        method=method
    )
    print(pText)
    with urllib.request.urlopen(request) as response:
        response_body = response.read().decode('utf-8')
