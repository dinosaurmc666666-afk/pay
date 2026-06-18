import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from mcrcon import MCRcon
from bakong_khqr import KHQR

app = Flask(__name__)
CORS(app)

# ----------------- កំណត់ព័ត៌មានបាកង (Bakong Config) -----------------
BAKONG_ACCOUNT = "pich_monthai@bkrt"
API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiMDMwNzUxOTE5NjBiNGVmYiJ9LCJpYXQiOjE3ODE3NDUwOTMsImV4cCI6MTc4OTUxNDY2MX0.Br3Nqd14phH6mJaW3TL81hsB3kEHvTy2gmY-E9acuOY"

khqr_client = KHQR(API_TOKEN)

# ----------------- កំណត់ព័ត៌មាន RCON Minecraft Server -----------------
RCON_HOST = "localhost"              
RCON_PORT = 25575                   
RCON_PASSWORD = "your_rcon_password" 

def send_minecraft_command(command):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as rcon:
            response = rcon.command(command)
            print(f"RCON Response: {response}")
            return True
    except Exception as e:
        print(f"No connection to RCON: {e}")
        return False

# ១. API សម្រាប់បង្កើតកូដ KHQR ផ្លូវការតាមរយៈបណ្ណាល័យ
@app.route('/api/generate-qr', methods=['POST'])
def generate_qr():
    data = request.json or {}
    order_id = data.get('orderId')
    amount = float(data.get('amount', 0))

    try:
        print(f"\n🔄 [REQUEST] Create a KHQR for Order: {order_id} pice: ${amount:.2f}...")
        
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
        
        print(f"[SUCCESS] Create a qr done")
        return jsonify({"status": "SUCCESS", "qrCode": qr_string})
            
    except Exception as e:
        print(f"[ERROR] Can't create KHQR: {str(e)}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

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
        md5_hash = khqr_client.generate_md5(qr_string)
        payment_status = khqr_client.check_payment(md5_hash)
        
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
    app.run(port=5000, debug=True)