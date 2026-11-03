from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

app = Flask(__name__)
CORS(app)  # للسماح بالاتصال من أي واجهة

# ==========================================
# 1. الواجهة (HTML مدمجة داخل السيرفر)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>أداة خصوصية إنستغرام</title>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background: #0a0a0a; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
        .box { background: #18181b; padding: 40px; border-radius: 16px; width: 100%; max-width: 450px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #27272a; }
        h1 { text-align: center; color: #ec4899; margin-bottom: 10px; font-size: 24px; }
        .subtitle { text-align: center; color: #888; font-size: 14px; margin-bottom: 30px; }
        .warning { background: #451a03; color: #fbbf24; padding: 12px; border-radius: 8px; font-size: 13px; margin-bottom: 20px; text-align: center; border: 1px solid #78350f; }
        input { width: 100%; padding: 14px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #333; background: #09090b; color: #fff; font-family: 'Tajawal'; box-sizing: border-box; font-size: 14px; }
        button { width: 100%; padding: 14px; border: none; border-radius: 8px; background: #ec4899; color: #fff; font-weight: bold; font-size: 15px; cursor: pointer; transition: 0.3s; margin-bottom: 10px; font-family: 'Tajawal'; }
        button:hover { background: #db2777; }
        button:disabled { background: #555; cursor: not-allowed; }
        #result { margin-top: 20px; padding: 15px; border-radius: 8px; text-align: center; display: none; font-weight: bold; font-size: 14px; }
        .success { background: #064e3b; color: #4ade80; border: 1px solid #166534; }
        .error { background: #7f1d1d; color: #f87171; border: 1px solid #991b1b; }
        .loading { background: #1e3a8a; color: #60a5fa; border: 1px solid #1e40af; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🛡️ أداة خصوصية إنستغرام</h1>
        <p class="subtitle">تطوير: عبدالرحمن وليد</p>
        
        <div class="warning">⚠️ استخدم الأداة على مسؤوليتك. قد تؤدي لمخالفة شروط إنستغرام.</div>
        
        <input type="password" id="session" placeholder="ضع الـ sessionid هنا...">
        
        <button onclick="doAction('hide_followers_following_list', true)">🙈 إخفاء المتابعين</button>
        <button onclick="doAction('hide_followers_following_list', false)">👁️ إظهار المتابعين</button>
        <button onclick="doAction('hide_story_from_followers', true)">📖 إخفاء الستوري</button>
        <button onclick="doAction('hide_activity_status', true)">🟢 إخفاء حالة النشاط</button>
        
        <div id="result"></div>
    </div>

    <script>
        async function doAction(settingId, value) {
            const session = document.getElementById('session').value.trim();
            const resultBox = document.getElementById('result');
            const buttons = document.querySelectorAll('button');
            
            if (!session) {
                resultBox.style.display = 'block';
                resultBox.className = 'error';
                resultBox.innerText = '⚠️ الرجاء إدخال الـ Session أولاً!';
                return;
            }

            buttons.forEach(b => b.disabled = true);
            resultBox.style.display = 'block';
            resultBox.className = 'loading';
            resultBox.innerText = '⏳ جاري التنفيذ...';

            try {
                const response = await fetch('/api/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session: session, setting_id: settingId, value: value })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultBox.className = 'success';
                    resultBox.innerText = '✅ ' + data.message;
                } else {
                    resultBox.className = 'error';
                    resultBox.innerText = '❌ ' + data.message;
                }
            } catch (error) {
                resultBox.className = 'error';
                resultBox.innerText = '❌ خطأ في الاتصال بالسيرفر.';
            } finally {
                buttons.forEach(b => b.disabled = false);
            }
        }
    </script>
</body>
</html>
"""

# ==========================================
# 2. دوال إنستغرام (العمليات الخلفية)
# ==========================================
def extract_user_id(sessionid):
    """استخراج رقم المستخدم من السيشن"""
    match = re.fullmatch(r"([1-9][0-9]*)(?::|%3[aA]).+", sessionid)
    if not match:
        raise ValueError("صيغة السيشن غير صحيحة. يجب أن تبدأ برقم المستخدم.")
    return match.group(1)

def instagram_mutation(sessionid, setting_id, value):
    """إرسال طلب التعديل لإنستغرام"""
    try:
        user_id = extract_user_id(sessionid)
        token = base64.b64encode(json.dumps({
            "ds_user_id": user_id,
            "sessionid": sessionid,
            "should_use_header_over_cookies": True
        }, separators=(",", ":")).encode()).decode("ascii")
        
        authorization = "Bearer IGT:2:" + token
        name = "IGSettingsBooleanMutation"
        
        form = {
            "method": "post", "format": "json", "server_timestamps": "true", "locale": "user",
            "fb_api_req_friendly_name": name, "client_doc_id": "2669261950526978627082629536",
            "variables": json.dumps({
                "setting_id": setting_id, "allow_error_codes": True,
                "callsite": "account_privacy", "value": value
            })
        }

        req = urllib.request.Request(
            "https://i.instagram.com/graphql/query",
            data=urllib.parse.urlencode(form).encode(),
            headers={
                "Authorization": authorization,
                "Cookie": f"sessionid={sessionid}; ds_user_id={user_id}",
                "IG-INTENDED-USER-ID": user_id,
                "X-IG-App-ID": "124024574287414",
                "X-Auth-Type": "instagram",
                "User-Agent": "Instagram 453.0.0",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=15) as res:
            body = json.loads(res.read())
            data = body.get("data", {})
            root = "xdt_api__v1__settings__set_bool"
            matches = [v for k, v in data.items() if k == root or k.startswith(root + "(")]
            
            if body.get("errors") or not matches or matches[0].get("value") is not True:
                return False, "فشل التعديل (تأكد من السيشن)."
            return True, "تم بنجاح!"
    except Exception as e:
        return False, f"خطأ: {str(e)}"

# ==========================================
# 3. مسارات السيرفر (Routes)
# ==========================================
@app.route('/')
def home():
    """عرض الواجهة الرئيسية"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/action', methods=['POST'])
def action():
    """استقبال الطلبات من الواجهة وتنفيذها"""
    data = request.json
    session = data.get('session')
    setting_id = data.get('setting_id')
    value = data.get('value')
    
    success, message = instagram_mutation(session, setting_id, value)
    return jsonify({"success": success, "message": message})

# ==========================================
# 4. التشغيل
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)