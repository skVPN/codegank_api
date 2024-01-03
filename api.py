from flask import *
import time
import sys
import SparkApi
import json
import os
import datetime
import requests 
import base64
import time
import yaml
import subprocess
import traceback
import re
import shelve
from loguru import logger
from config import appid,api_secret,api_key,port
# 作者 : codegank

logger.add('log.log', format="{time} {level} {message}")


app = Flask(__name__)
DB = shelve.open('codegank.db') 
def get_local_ip():
    try:
        ip_address=subprocess.check_output(['hostname','-I']).decode().split(' ')
        if ip_address:
            return ip_address[0]
    except:
        return "无法获取本机局域网IP地址"

local_ip = get_local_ip()
print("本机局域网IP地址: ", local_ip)

clipboard = []
file_list = []
@app.route('/download/<path:filename>')
def download_file(filename):
    data_dir = os.path.join(app.root_path, 'files')
    return send_file(os.path.join(data_dir, filename))

@app.route('/clipboard', methods=['GET', 'POST'])
def handle_clipboard():
    if request.method == 'GET':
        response = '<h1>Clipboard</h1>'
        for item in clipboard[:10]:
            response += f'<p>[{item["time"]}] {item["ip"]}: {item["text"]}</p>'
        return response
    elif request.method == 'POST':
        post_data = request.form['text']
        data={
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip': request.remote_addr,
            'text': post_data
        }
        clipboard.append(data)
        with open ('clipboard.bak','a+') as f:
            f.write(json.dumps(data))
        return redirect(url_for('index'))

@app.route('/files', methods=['GET', 'POST'])
def handle_files():
    if request.method == 'GET':
        response = '<h1>File List</h1>'
        for item in file_list[-10:]:
            response += f'<p>[{item["time"]}] {item["ip"]}: {item["filename"]},<a href="{item["filename"]}" download>下载</a></p>'
        return response
    elif request.method == 'POST':
        file_data = request.files['file'].read()
        filename = request.files['file'].filename
        data_dir = os.path.join(app.root_path, 'files')
        with open(os.path.join(data_dir,filename), 'wb') as file:
            file.write(file_data)
        file_list.append({
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip': request.remote_addr,
            'filename': filename
        })
        return redirect(url_for('index'))

@app.route('/getconfig', methods=['GET'])
def generate_clash_config():
    config = request.args.get('config')
    _info = config.split(":")
    ip = _info[0]
    port = _info[1]
    user_name = _info[2]
    pwd = _info[3]
    name = "SOCKS5-%s" % ip
    config = {
     "dns":{
    "ipv6": False,
    "default-nameserver": ['223.5.5.5', '119.29.29.29'],
    "enhanced-mode": "fake-ip",
    "fake-ip-range": "198.18.0.1/16",
    "use-hosts": True,
    "nameserver": ['https://doh.pub/dns-query', 'https://dns.alidns.com/dns-query'],
    "fallback": ['https://doh.dns.sb/dns-query', 'https://dns.cloudflare.com/dns-query', 'https://dns.twnic.tw/dns-query', 'tls://8.8.4.4:853'],
    "fallback-filter": { 'geoip': True, 'ipcidr': ["240.0.0.0/4", "0.0.0.0/32"] }
                },
        "proxies": [
            {
                "name": name,
                "type": "socks5",
                "server": ip,
                "port": int(port),
                "username": user_name,
                "password": pwd
            }
        ],
        "proxy-groups": [
            {
                "name": "Proxy Group",
                "type": "select",
                "proxies": [
                    name
                ]
            }
        ],
        "rules":[
            "IP-CIDR,0.0.0.0/8,DIRECT",
            "IP-CIDR,10.0.0.0/8,DIRECT",
            "IP-CIDR,127.0.0.0/8,DIRECT",
            "IP-CIDR,169.254.0.0/16,DIRECT",
            "IP-CIDR,172.16.0.0/12,DIRECT",
            "IP-CIDR,192.168.0.0/16,DIRECT",
            "IP-CIDR,224.0.0.0/4,DIRECT",
            "IP-CIDR,240.0.0.0/4,DIRECT",
            "MATCH,*,Proxy Group"
            ]
    }
    config_yaml = yaml.dump(config)
    return config_yaml

@app.route('/generate_clash_config', methods=['GET'])
def handle_generate_clash_config():
    name = request.args.get('config')
    _info = name.split(":")
    ip = _info[0]
    clash_url = f"http://{local_ip}:{port}/getconfig?config={name}"
    clipboard.append({
        'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ip': request.remote_addr,
        'text': clash_url
    })
    print("Clipboard+++", clash_url)
    return redirect(url_for('index'))

def gpt(Input):
    """
    https://www.xfyun.cn/doc/spark/Web.html#_1-%E6%8E%A5%E5%8F%A3%E8%AF%B4%E6%98%8E
    计费包含接口的输入和输出内容

    1tokens 约等于1.5个中文汉字 或者 0.8个英文单词

    星火V1.5支持[搜索]内置插件；星火V2.0和V3.0支持[搜索]、[天气]、[日期]、[诗词]、[字词]、[股票]六个内置插件
"""
    #用于配置大模型版本，默认“general/generalv2”
    domain = "general"   # v1.5版本
    # domain = "generalv2"    # v2.0版本
    #云端环境的服务地址
    Spark_url = "ws://spark-api.xf-yun.com/v1.1/chat"  # v1.5环境的地址
    #Spark_url = "ws://spark-api.xf-yun.com/v2.1/chat"  # v2.0环境的地址


    # length = 0
    text=[]
    def getText(role,content):
        jsoncon = {}
        jsoncon["role"] = role
        jsoncon["content"] = content
        text.append(jsoncon)
        return text

    def getlength(text):
        length = 0
        for content in text:
            temp = content["content"]
            leng = len(temp)
            length += leng
        return length

    def checklen(text):
        print (f"length:{getlength(text)}-{text}")
        while (getlength(text) > 8000):
            del text[0]
        return text
    question = checklen(getText("user",Input))
    print (f"question:{question}")

    SparkApi.answer =""
    print("星火:",end = "")
    SparkApi.main(appid,api_key,api_secret,Spark_url,domain,question)
    getText("assistant",SparkApi.answer)
    return  SparkApi.answer


@app.route('/wx',methods=['GET','POST'])
def wx():
    url ="http://localhost:3001/webhook/msg"
    data=dict(request.form)
    _type= re.findall('"type":(\d+?)',data['source'])
    print (str(data),_type,'text' not in str(data)) 
    content = data.get('content','').strip()
    source =json.loads(data['source'])
    is_new =False
    room = source['room']
    payload={}
    if type(room) ==dict:
        payload= room.get('payload',{})
    isRoom =False
    _topic = re.findall('"topic":"(.*?)"',data['source'])
    if _topic:
        name = _topic[0]
        isRoom =True
    else:
        name= re.findall('"name":"(.*?)"',data['source'])[-1]
        
    new_memberIdList = len(payload.get('memberIdList',[]))
    print (f'++{name}-总人数:{new_memberIdList}') 
    #if new_memberIdList>DB.get(name,0)and not content and 0:
    if not content and 1:
        #global memberIdList
        is_new=True 
    #DB[name] =new_memberIdList
       
    #print (f'content:{content}-{isRoom}')
    print (isRoom, '@gpt' not in content, int(_type[0]),name, 'text' not in str(data)) 
    if isRoom  and '@gpt' not in content and _type and int(_type[0])==1 and 'text' not in str(data) and 'img' not in str(data) and str(data).count('type')==2:
        res = f"欢迎新同学入群！请查看群公告获取最新的资料!。\n我是群主的AI机器人助理，有任何需要可以艾特我哦。"
        time.sleep(2)
        ret = requests.post(url,json={"to":name,"isRoom":isRoom,"type":"text","content":res},timeout=10).text
        return {}
    if isRoom and  content in ['gpt','代理','x-ui']:
        
        ret="""1元服务器确认当前已经没有库存了，等有了库存会在群里第一时间发出来
4G代理IP体验和x-ui体验目前正常
x-ui地址：http://45.15.10.27:5000/xui/inbounds
chat-gpt体验：http://ai.myip.fun/
9.9的云服务器https://www.juanidc.com/cart
其他待踩坑实践的免费云服务
1,甲骨文-性能最强
2,aws 要信用卡一年"""
        print ('send')
        print (requests.post(url,json={"to":name,"isRoom":isRoom,"type":"text","content":ret}).text)
        return

    #print ('need gpt',room,name,content)
    res=None
    if content and '@gpt' in content:
        content = content.replace('@gpt','')
        if 'biying' in content:
            ret = gpt0(content)
        else:
            ret = gpt(content)
        res = f"ques:{content}\nanswer:{ret}"
        logger.info(json.dumps({"to":name,"isRoom":isRoom,"type":"text","content":res}))
        
        for i in range(3):
            ret = requests.post(url,json={"to":name,"isRoom":isRoom,"type":"text","content":res},timeout=10).text
            print ('ret:',ret,i)
            if 'success' in ret:
                break 
    return {'hello':"mylove"}

@app.route('/')
def index():
    print (clipboard,'+'*9,clipboard[:10:-1])
    return render_template('index.html', clipboard=clipboard[::-1][:5], files=file_list[::-1][:6],ct=str(time.time()))

@app.route('/gpt')
def my_gpt():
    text =request.args.get('text')
    print ('get,text',text)
    ret = gpt(text)
    return jsonify(json.loads(ret))

if __name__ == '__main__':
    #app.run(host='0.0.0.0', port=443,ssl_context=("wx.myip.fun.pem","wx.myip.fun.key"))
    app.run(host='0.0.0.0', port=port)
