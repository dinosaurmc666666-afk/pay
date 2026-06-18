import hashlib
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from mcrcon import MCRcon
from bakong_khqr import KHQR

app = Flask(__name__)
CORS(app)

# ----------------- កំណត់ព័ត៌មានបាកង (Bakong Config) -----------------
BAKONG_ACCOUNT = "pich_monthai@bkrt"
API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiMDMwNzUxOTE5NjBiNGVmYiJ9LCJpYXQiOjE3ODE3NDUwOTMsImV4cCI6MTcាយ៥១៤៦៦MX0.Br3Nqd14phH6mJaW3TL81hsB3kEHvTy2gmY-E9acuOY"

try:
    khqr_client = KHQR(API_TOKEN)
except Exception as e:
    print(f"⚠️ មិនអាចទាញយកបណ្ណាល័យ KHQR បានពេញលេញទេ ប៉ុន្តែប្រព័ន្ធ Fallback នឹងជួយបង្កើត QR ជំនួស: {e}")
    khqr_client = None

# ----------------- កំណត់ព័ត៌មាន RCON Minecraft Server -----------------
RCON_HOST = "localhost"              
RCON_PORT = 25575                   
RCON_PASSWORD = "your_rcon_password" 

def send_minecraft_command(command):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as rcon:
            response = rcon.command(command)
            print(f"🖥️ RCON Response: {response}")
            return True
    except Exception as e:
        print(f"❌ No connection to RCON: {e}")
        return False

# 💡 មុខងារពិសេស៖ បង្កើត KHQR តាមរូបមន្តស្តង់ដារ (ទោះ API ខាងក្រៅគាំង ក៏បង្កើតចេញមកស្កែនបានដែរ)
def generate_backup_khqr(account, amount, order_id):
    merchant_name = "FOREST-SMP"
    merchant_city = "Phnom Penh"
    
    # ផ្សំកូដតាមទម្រង់ EMVCo របស់បាកង
    khqr = f"00020101021230520011ca.com.bakong0115{account}520459995303840"
    if amount > 0:
        amt_str = f"{amount:.2f}"
        khqr += f"54{len(amt_str):02d}{amt_str}"
    khqr += f"5802KH59{len(merchant_name):02d}{merchant_name}60{len(merchant_city):02d}{merchant_city}"
    
    # ភ្ជាប់ Order ID ចូលក្នុង Bill
    additional_data = f"01{len(order_id):02d}{order_id}"
    khqr += f"62{len(additional_data):02d}{additional_data}6304"
    
    # គណនា CRC16 Checksum
    crc = 0xFFFF
    for char in khqr.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return khqr + f"{crc:04X}"

# ១. API សម្រាប់បង្កើតកូដ KHQR
@app.route('/api/generate-qr', methods=['POST'])
def generate_qr():
    data = request.json or {}
    order_id = data.get('orderId', 'FMC999')
    amount = float(data.get('amount', 0))

    print(f"\n🔄 [REQUEST] Create a KHQR for Order: {order_id} price: ${amount:.2f}...")
    
    # ព្យាយាមប្រើប្រាស់បណ្ណាល័យផ្លូវការជាមុនសិន
    if khqr_client:
        try:
            qr_string = khqr_client.create_qr(
                account_id=BAKONG_ACCOUNT,
                merchant_name='FOREST-SMP',
                merchant_city='Phnom Penh',
                amount=amount,
                currency='USD',  
                store_label='ForestMC',
                bill_number=order_id,
                static=False
            )
            print(f"✅ [SUCCESS] Created QR via Bakong Library")
            return jsonify({"status": "SUCCESS", "qrCode": qr_string})
        except Exception as e:
            print(f"⚠️ [BAKONG ERROR] បណ្ណាល័យបាកងជួបបញ្ហា: {str(e)} -> កំពុងប្តូរទៅប្រើប្រាស់ប្រព័ន្ធជំនួស...")

    # 🛠️ ប្រព័ន្ធជំនួស (Fallback Mode) រត់ស្វ័យប្រវត្តក្នុងករណី API ខាងលើដួល ការពារកុំឱ្យគាំងលោត Error 500
    try:
        backup_qr = generate_backup_khqr(BAKONG_ACCOUNT, amount, order_id)
        print(f"✅ [FALLBACK SUCCESS] Created QR via Backup Generator")
        return jsonify({"status": "SUCCESS", "qrCode": backup_qr})
    except Exception as err:
        print(f"❌ [CRITICAL ERROR] មិនអាចបង្កើត QR បានទាំងពីរប្រព័ន្ធ: {str(err)}")
        return jsonify({"status": "ERROR", "message": str(err)}), 500

# ២. API សម្រាប់ឆែកលុយដោយប្រើ MD5 Hash
@app.route('/api/check-payment', methods=['POST'])
def check_payment():
    data = request.json or {}
    order_id = data.get('orderId')
    username = data.get('username')
    rank_name = data.get('rankName', '').lower()
    qr_string = data.get('qrCode') 

    if not qr_string:
        return jsonify({"status": "PENDING", "message": "Missing QR code string"})

    try:
        # បង្កើត MD5 ផ្ទាល់ខ្លួន បើទោះជាទាញចេញពីបណ្ណាល័យ ឬកូដខាងក្រៅ
        if khqr_client:
            md5_hash = khqr_client.generate_md5(qr_string)
            payment_status = khqr_client.check_payment(md5_hash)
        else:
            md5_hash = hashlib.md5(qr_string.encode('utf-8')).hexdigest()
            url = f"https://api-bakong.nbc.gov.kh/v1/check_transaction_by_md5/{md5_hash}"
            headers = {"Authorization": f"Bearer {API_TOKEN}"}
            response = requests.get(url, headers=headers, timeout=5)
            res_data = response.json()
            payment_status = "PAID" if (response.status_code == 200 and res_data.get('responseCode') == 0) else "PENDING"
        
        print(f"🔄 [CHECKING] Order: {order_id} | Status: {payment_status}")

        if payment_status == "PAID":
            print(f"💰 [PAYMENT SUCCESS] {order_id}!")
            
            command = f"lp user {username} parent set {rank_name}"
            rcon_success = send_minecraft_command(command)
            
            return jsonify({
                "status": "PAID",
                "message": "Payment successful!",
                "rconStatus": "SUCCESS" if rcon_success else "RCON_FAILED"
            })

        return jsonify({"status": "PENDING", "message": "Waiting..."})
        
    except Exception as e:
        return jsonify({"status": "PENDING", "message": "Checking..."})

if __name__ == '__main__':
    # កែសម្រួលឱ្យទាញយក Port របស់ Cloud ស្វ័យប្រវត្តក្នុងករណីយកទៅ Deploy
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
