# -*- coding: utf-8 -*-
"""诊断: 通过 DoH 获取 hf-mirror.com 真实 IP 并做 TLS 验证"""
import json
import socket
import ssl
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def doh(url, headers=None):
    req = urllib.request.Request(
        url, headers=headers or {"accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def main():
    ips = set()
    sources = [
        ("AliDoH", "https://dns.alidns.com/resolve?name=hf-mirror.com&type=A"),
        ("DNSPod", "https://doh.pub/dns-query?name=hf-mirror.com&type=A"),
        ("Cloudflare", "https://cloudflare-dns.com/dns-query?name=hf-mirror.com&type=A"),
    ]
    for name, url in sources:
        try:
            j = doh(url)
            for a in j.get("Answer", []):
                if a.get("type") == 1:
                    ips.add(a["data"])
                    print(f"{name}: {a['data']}")
        except Exception as e:
            print(f"{name}: FAIL {str(e)[:80]}")

    print("候选IP:", ips)
    for ip in sorted(ips):
        if ip.startswith("28."):
            print(f"跳过假IP: {ip}")
            continue
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((ip, 443), timeout=10) as s:
                with ctx.wrap_socket(s, server_hostname="hf-mirror.com") as ss:
                    ss.sendall(
                        b"GET /Systran/faster-whisper-small/resolve/main/config.json "
                        b"HTTP/1.1\r\nHost: hf-mirror.com\r\nConnection: close\r\n\r\n")
                    data = ss.recv(500).decode("latin1")
                    first = data.split("\r\n")[0]
                    print(f"IP {ip} TLS验证: {first}")
                    if "200" in first:
                        print(f">>> 可用IP: {ip}")
        except Exception as e:
            print(f"IP {ip} 验证失败: {str(e)[:80]}")


if __name__ == "__main__":
    main()
