import requests
import os
from datetime import datetime
import pytz
from bs4 import BeautifulSoup

# --- ส่วนตั้งค่าหลัก ---
SINGBURI_WATER_URL = "https://singburi.thaiwater.net/wl"
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_API_URL = "https://api.line.me/v2/bot/message/broadcast"

# --- ส่วนที่ 1: ฟังก์ชันดึงข้อมูล (ปรับปรุงใหม่ทั้งหมด) ---

def get_singburi_data(url):
    """ดึงข้อมูลระดับน้ำจากเว็บ singburi.thaiwater.net"""
    try:
        print("กำลังเชื่อมต่อกับ singburi.thaiwater.net...")
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        if not table:
            print("ไม่พบตารางข้อมูลในหน้าเว็บ")
            return None
            
        rows = table.find('tbody').find_all('tr')
        
        for row in rows:
            if 'อินทร์บุรี' in row.text:
                print("พบแถวข้อมูลของ 'อินทร์บุรี' แล้ว")
                columns = row.find_all('td')
                water_level = float(columns[2].text.strip())
                print(f"ดึงข้อมูลสำเร็จ: ระดับน้ำ {water_level} ม.รทก.")
                return water_level
        
        print("วนลูปจนสุด แต่ไม่พบแถวข้อมูลของ 'อินทร์บุรี'")
        return None
        
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก {url}: {e}")
        return None

def get_dam_discharge_from_file():
    """อ่านข้อมูลการระบายน้ำของเขื่อนจากไฟล์ dam_data.txt"""
    try:
        print("กำลังอ่านข้อมูลเขื่อนจากไฟล์ dam_data.txt...")
        with open('dam_data.txt', 'r') as f:
            discharge_rate = float(f.read().strip())
        print(f"อ่านข้อมูลสำเร็จ: เขื่อนระบายน้ำ {discharge_rate} ลบ.ม./วินาที")
        return discharge_rate
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการอ่านไฟล์ dam_data.txt: {e}")
        return 1000 # คืนค่า default ที่ปลอดภัยหากอ่านไฟล์ไม่ได้

# --- ส่วนที่ 2: ฟังก์ชันวิเคราะห์และสร้างข้อความ (เหมือนเดิม) ---
def analyze_and_create_message(inburi_level, dam_discharge):
    if inburi_level is None:
        return "เกิดข้อผิดพลาด: ไม่สามารถดึงข้อมูลระดับน้ำอินทร์บุรีได้ กรุณาตรวจสอบเว็บไซต์ singburi.thaiwater.net"

    bank_height = 13.0
    distance_to_bank = bank_height - inburi_level
    
    if dam_discharge > 2400 or distance_to_bank < 1.0:
        status_emoji = "🟥"
        status_title = "‼️ ประกาศเตือนภัยระดับสูงสุด ‼️"
        recommendation = ("คำแนะนำ:\n1. เตรียมพร้อมอพยพหากอยู่ในพื้นที่เสี่ยง\n2. ขนย้ายทรัพย์สินขึ้นที่สูงโดยด่วน\n3. งดใช้เส้นทางสัญจรริมแม่น้ำ")
    elif dam_discharge > 1800 or distance_to_bank < 2.0:
        status_emoji = "🟨"
        status_title = "‼️ ประกาศเฝ้าระวัง ‼️"
        recommendation = ("คำแนะนำ:\n1. บ้านเรือนริมตลิ่งนอกคันกั้นน้ำ ให้เริ่มขนของขึ้นที่สูง\n2. ติดตามสถานการณ์อย่างใกล้ชิด")
    else:
        status_emoji = "🟩"
        status_title = "สถานะปกติ"
        recommendation = "สรุป: สถานการณ์น้ำยังปกติ ไม่น่ากังวล ขอให้ประชาชนใช้ชีวิตได้ตามปกติครับ"

    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    
    message = (
        f"{status_emoji} {status_title}\n"
        f"รายงานสถานการณ์น้ำเจ้าพระยา อ.อินทร์บุรี\n"
        f"ประจำวันที่: {now.strftime('%d/%m/%Y %H:%M')} น.\n\n"
        f"• ระดับน้ำ (อินทร์บุรี): {inburi_level:.2f} ม.รทก.\n"
        f"  (ต่ำกว่าตลิ่งที่ตั้งค่าไว้ {distance_to_bank:.2f} ม.)\n"
        f"• เขื่อนเจ้าพระยา (ข้อมูลล่าสุดที่คุณป้อน): {dam_discharge:,.0f} ลบ.ม./วินาที\n\n"
        f"{recommendation}"
    )
    return message

# --- ส่วนที่ 3: ฟังก์ชันส่งข้อความไปที่ LINE (เหมือนเดิม) ---
def send_line_broadcast(message):
    if not LINE_TOKEN:
        print("ไม่พบ LINE_CHANNEL_ACCESS_TOKEN")
        return
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": message}]}
    try:
        response = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print("ส่งข้อความ Broadcast สำเร็จ!")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการส่ง LINE Broadcast: {e}")

# --- ส่วนทำงานหลัก (Main) ---
if __name__ == "__main__":
    print("===== เริ่มการทำงานของระบบเฝ้าระวังน้ำ v4.0 (Final) =====")
    
    # 1. ดึงข้อมูล
    inburi_level = get_singburi_data(SINGBURI_WATER_URL)
    dam_discharge = get_dam_discharge_from_file()
    
    # 2. วิเคราะห์และสร้างข้อความ
    final_message = analyze_and_create_message(inburi_level, dam_discharge)
    print("\n--- ข้อความที่จะส่ง ---")
    print(final_message)
    print("---------------------\n")
    
    # 3. ส่งข้อความ
    send_line_broadcast(final_message)
        
    print("===== การทำงานเสร็จสิ้น =====")
