import requests
import os
from datetime import datetime
import pytz
from bs4 import BeautifulSoup # <-- เราจะใช้เครื่องมือใหม่นี้

# --- ส่วนตั้งค่าหลัก ---
# URL สำหรับดึงข้อมูล (อัปเดตตามที่คุณให้มา)
SINGBURI_WATER_URL = "https://singburi.thaiwater.net/wl"
# URL สำรองสำหรับข้อมูลเขื่อน (ใช้จากคลังข้อมูลน้ำแห่งชาติ)
DAM_URL = "https://water.onwr.go.th/api/v1/stations/dam/100101/historical"

# กุญแจสำหรับส่ง LINE
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_API_URL = "https://api.line.me/v2/bot/message/broadcast"

# --- ส่วนที่ 1: ฟังก์ชันดึงข้อมูล (ปรับปรุงใหม่ทั้งหมด) ---

def get_singburi_data(url):
    """ดึงข้อมูลระดับน้ำจากเว็บ singburi.thaiwater.net"""
    try:
        print("กำลังเชื่อมต่อกับ singburi.thaiwater.net...")
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        
        # ใช้ BeautifulSoup เพื่อค้นหาข้อมูลในหน้าเว็บ
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ค้นหาแถวของ "อินทร์บุรี"
        # เราจะหา tag 'a' ที่มีข้อความ "อินทร์บุรี" แล้วหาพ่อแม่ของมันคือแถว <tr>
        inburi_link = soup.find('a', string=lambda text: 'อินทร์บุรี' in text)
        if not inburi_link:
            print("ไม่พบแถวข้อมูลของ 'อินทร์บุรี' ในหน้าเว็บ")
            return None, None

        inburi_row = inburi_link.find_parent('tr')
        
        # ค้นหาคอลัมน์ทั้งหมดในแถวนั้น
        columns = inburi_row.find_all('td')
        
        # ดึงข้อมูลจากคอลัมน์ที่ถูกต้องตามโครงสร้างที่คุณส่งมา
        # คอลัมน์ที่ 1: ชื่ออำเภอ
        # คอลัมน์ที่ 2: ระดับน้ำปัจจุบัน (ม.รทก.)
        # คอลัมน์ที่ 3: ระดับตลิ่งของเว็บ
        water_level_str = columns[2].text.strip()
        water_level = float(water_level_str)
        
        print(f"พบข้อมูลอินทร์บุรี: ระดับน้ำ {water_level} ม.รทก.")
        return water_level
        
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก {url}: {e}")
        return None

def get_dam_discharge():
    """ดึงข้อมูลการระบายน้ำล่าสุดจาก API ของ สทนช."""
    try:
        print("กำลังเชื่อมต่อกับ API ข้อมูลเขื่อน...")
        # ดึงข้อมูลย้อนหลัง 1 วัน
        params = {'day': 1}
        response = requests.get(DAM_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        # เอาข้อมูลตัวล่าสุด (ตัวสุดท้ายใน list)
        latest_data = data[-1]
        # ค้นหาค่าการระบายน้ำ (discharge)
        discharge_rate = latest_data.get('discharge')
        
        if discharge_rate is None:
            print("ไม่พบข้อมูล 'discharge' ใน API ตอบกลับ")
            return None
        
        print(f"พบข้อมูลเขื่อนเจ้าพระยา: ระบายน้ำ {discharge_rate} ลบ.ม./วินาที")
        return float(discharge_rate)

    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการดึงข้อมูลเขื่อนจาก API: {e}")
        return None

# --- ส่วนที่ 2: ฟังก์ชันวิเคราะห์และสร้างข้อความ ---
def analyze_and_create_message(inburi_level, dam_discharge):
    """วิเคราะห์ข้อมูลและสร้างข้อความสำหรับส่ง LINE"""
    if inburi_level is None or dam_discharge is None:
        return "เกิดข้อผิดพลาด: ไม่สามารถดึงข้อมูลสำคัญเพื่อทำการวิเคราะห์ได้ กรุณาตรวจสอบ Log"

    # *** อัปเดตระดับตลิ่งเป็น 13 เมตร ตามที่คุณต้องการ ***
    bank_height = 13.0
    distance_to_bank = bank_height - inburi_level
    
    # ตรรกะการตัดสินใจ (เหมือนเดิม)
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
        f"• เขื่อนเจ้าพระยา: ระบายน้ำ {dam_discharge:,.0f} ลบ.ม./วินาที\n\n"
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
    print("===== เริ่มการทำงานของระบบเฝ้าระวังน้ำ v3.0 =====")
    
    # 1. ดึงข้อมูล
    inburi_level = get_singburi_data(SINGBURI_WATER_URL)
    dam_discharge = get_dam_discharge()
    
    # 2. วิเคราะห์และสร้างข้อความ
    final_message = analyze_and_create_message(inburi_level, dam_discharge)
    print("\n--- ข้อความที่จะส่ง ---")
    print(final_message)
    print("---------------------\n")
    
    # 3. ส่งข้อความ
    send_line_broadcast(final_message)
        
    print("===== การทำงานเสร็จสิ้น =====")
