import time
import uuid
import jwt
import requests
import os
from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # 处理 CORS 预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        self.do_POST()  # 简化处理，GET 和 POST 都走同一个逻辑
    
    def do_POST(self):
        # 1. 从请求中获取学生学号
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = json.loads(self.rfile.read(content_length))
            student_id = body.get('student_id', 'anonymous')
        else:
            student_id = self.path.split('student_id=')[-1].split('&')[0] if 'student_id=' in self.path else 'anonymous'
        
        # 2. 从环境变量读取配置（这些稍后在 Vercel 后台设置）
        APP_ID = os.environ.get('COZE_APP_ID')
        KID = os.environ.get('COZE_KID')
        PRIVATE_KEY = os.environ.get('COZE_PRIVATE_KEY').replace('\\n', '\n')
        
        if not all([APP_ID, KID, PRIVATE_KEY]):
            self._send_response(500, {'error': '服务器配置错误，缺少环境变量'})
            return
        
        try:
            # 3. 生成 JWT（关键：session_name 设置为学生学号）
            payload = {
                'iss': APP_ID,
                'aud': 'api.coze.cn',
                'iat': int(time.time()),
                'exp': int(time.time()) + 600,  # 10分钟有效
                'jti': str(uuid.uuid4()),
                'session_name': student_id      # 🚀 实现会话隔离的关键！
            }
            headers = {
                'kid': KID,
                'typ': 'JWT',
                'alg': 'RS256'
            }
            jwt_token = jwt.encode(payload, PRIVATE_KEY, algorithm='RS256', headers=headers)
            
            # 4. 用 JWT 换取 access_token
            token_url = 'https://api.coze.cn/api/permission/oauth2/token'
            token_headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {jwt_token}'
            }
            token_data = {
                'duration_seconds': 86400,  # 24小时
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer'
            }
            
            response = requests.post(token_url, headers=token_headers, json=token_data)
            result = response.json()
            
            if 'access_token' in result:
                self._send_response(200, {
                    'success': True,
                    'access_token': result['access_token'],
                    'expires_in': result.get('expires_in', 86400),
                    'student_id': student_id
                })
            else:
                self._send_response(500, {'error': f'获取token失败: {result}'})
                
        except Exception as e:
            self._send_response(500, {'error': str(e)})
    
    def _send_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())