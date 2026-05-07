#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare DNS 更新器
获取优选 IP 并更新 Cloudflare DNS 记录
"""

from asyncio import current_task
import json
import traceback
import time
import os

import requests
from cloudflare import Cloudflare
from dotenv import load_dotenv

load_dotenv()

# API 配置
CF_API_TOKEN = os.environ.get("CF_API_TOKEN")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID")
CF_DNS_NAME = os.environ.get("CF_DNS_NAME")
# 优选 IP URL
CF_YX_URL = os.environ.get("CF_YX_URL") or "https://ip.164746.xyz/ipTop.html"
# pushplus_token
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 请求头
HEADERS = {
    'Authorization': f'Bearer {CF_API_TOKEN}',
    'Content-Type': 'application/json'
}

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30


def get_cf_speed_test_ip(timeout=10, max_retries=5):
    """
    获取 Cloudflare 优选 IP

    Args:
        timeout: 单次请求超时时间
        max_retries: 最大重试次数

    Returns:
        优选 IP 字符串，失败返回 None
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(
                CF_YX_URL,
                timeout=timeout
            )
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"获取优选 IP 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                traceback.print_exc()
    return None

# 解析优选 IP
def parse_ip_addresses(ip_str):
    """
    解析优选 IP 字符串，提取 IP 地址

    Args:
        ip_str: 优选 IP 字符串，格式为 "IP:IP:IP:IP"

    Returns:
        IP 地址字符串，失败返回 None
    """
    if not ip_str:
        print("错误: 缺少必要的参数 (ip_str)")
        return None
    ip_addresses = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
    if not ip_addresses:
        print("错误: 未解析到有效 IP 地址")
        return None
    print(f"解析到 {len(ip_addresses)} 个 IP 地址")
    return ip_addresses

def get_dns_records(name):
    """
    获取指定名称的 DNS 记录列表

    Args:
        name: DNS 记录名称

    Returns:
        记录字典列表（包含 id, name, type, content, comment），失败返回空列表
    """
    client = Cloudflare(
        api_token=CF_API_TOKEN,
    )
    current_page = 0
    current_count = 0
    total_count = 0
    records = []
    while current_page == 0 or current_count < total_count:
        current_page += 1
        page = client.dns.records.list(
            zone_id=CF_ZONE_ID,
            name=name,
            page=current_page,
            per_page=20,
        )
        if not page or not page.result or not page.result_info:
            break

        for record in page.result:
            records.append({
                'id': record.id,
                'name': record.name,
                'type': record.type,
                'content': record.content,
                'comment': record.comment,
            })
        # 当前获取的总记录数
        current_count += len(page.result)
        # 总记录数
        total_count = page.result_info.total_count
        print(f"总记录数: {total_count}，当前记录数: {current_count}")
    
    print(f"获取记录数: {len(records)}")
    return records

def add_dns_record(name, cf_ip):
    """
    创建 DNS 记录

    Args:
        name: DNS 记录名称
        cf_ip: 新的 IP 地址

    Returns:
        操作结果字符串
    """
    if not name or not cf_ip:
        print("错误: 缺少必要的参数 (name, cf_ip)")
        return

    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    client = Cloudflare(
        api_token=CF_API_TOKEN,
    )

    record_response = client.dns.records.create(
        zone_id=CF_ZONE_ID,
        name=name,
        content=cf_ip,
        ttl=3600,
        type="A",
        comment=f"{current_time}",
    )
    if record_response:
        print(f"dns add success: ---- Time: {current_time} ---- ip：{cf_ip}")
        return f"ip:{cf_ip} 解析 {name} 成功\n"
    else:
        print(f"dns add ERROR: ---- Time: {current_time} ---- ip：{cf_ip} ---- MESSAGE: {record_response.errors}")
        return f"ip:{cf_ip} 解析 {name} 失败\n"

def del_dns_record(record_id):
    """
    删除 DNS 记录

    Args:
        record_id: DNS 记录 ID

    Returns:
        操作结果字符串
    """
    if not record_id:
        print("错误: 缺少必要的参数 (record_id)")
        return

    client = Cloudflare(
        api_token=CF_API_TOKEN,
    )
    record = client.dns.records.delete(
        dns_record_id=record_id,
        zone_id=CF_ZONE_ID,
    )
    return record

def del_dns_records(records):
    """
    删除多个 DNS 记录

    Args:
        records: 包含 DNS 记录 ID 的列表

    Returns:
        操作结果字符串
    """
    if not records:
        print("错误: 缺少必要的参数 (records)")
        return

    for record in records:
        del_dns_record(record['id'])

def push_plus(content):
    """
    发送 PushPlus 消息推送

    Args:
        content: 消息内容
    """
    if not PUSHPLUS_TOKEN:
        print("PUSHPLUS_TOKEN 未设置，跳过消息推送")
        return

    url = 'http://www.pushplus.plus/send'
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "IP优选DNSCF推送",
        "content": content,
        "template": "markdown",
        "channel": "wechat"
    }

    try:
        body = json.dumps(data).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        requests.post(url, data=body, headers=headers, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        print(f"消息推送失败: {e}")

def main():
    """主函数"""
    # 检查必要的环境变量
    if not all([CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME]):
        print("错误: 缺少必要的环境变量 (CF_API_TOKEN, CF_ZONE_ID, CF_DNS_NAME)")
        return

    # 获取最新优选 IP
    ip_addresses_str = get_cf_speed_test_ip()
    if not ip_addresses_str:
        print("错误: 无法获取优选 IP")
        return

    ip_addresses = parse_ip_addresses(ip_addresses_str)
    if not ip_addresses:
        print("错误: 未解析到有效 IP 地址")
        return

    # 获取 DNS 记录
    dns_records = get_dns_records(CF_DNS_NAME) or []
    # 更新 DNS 记录
    push_plus_content = []
    # 删除之前存在的 DNS 记录
    for index, ip_address in enumerate(dns_records):
        dns = del_dns_record(dns_records[index]['id'])

    # 新增 新获取的 DNS 记录
    for index, ip_address in enumerate(ip_addresses):
        dns = add_dns_record(CF_DNS_NAME, ip_address)
        push_plus_content.append(dns)

    # 发送推送
    if push_plus_content:
        print(push_plus_content)
        push_plus('\n'.join(push_plus_content))

if __name__ == '__main__':
    main()
