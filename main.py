import requests
import os
from datetime import datetime
import pytz
from bs4 import BeautifulSoup

# --- ค่าคงที่และตัวแปรหลัก ---
SINGBURI_WATER_URL = "https://singburi.thaiwater.net/wl"
LINE_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_API_URL = "https://api.line.me/v2/bot/message/broadcast"

def get_singburi_data(url):
    """
    ดึงข้อมูลระดับน้ำจากเว็บ singburi.thaiwater.net สำหรับสถานี 'อินทร์บุรี'
    (ปรับปรุงล่าสุดตามโครงสร้าง HTML ที่ได้รับ)
    """
    try:
        print("กำลังเชื่อมต่อกับ singburi.thaiwater.net...")
        response = requests.get(url, timeout=30)
        response.raise_for_status() # ตรวจสอบว่าการเชื่อมต่อสำเร็จหรือไม่

        soup = BeautifulSoup(response.text, 'html.parser')

        # ค้นหาทุกแถว (tr) ในตาราง
        rows = soup.find_all("tr")
        if not rows:
            print("❌ ไม่พบแถวข้อมูล (<tr>) ใดๆ ในหน้าเว็บ")
            return None

        print(f"ค้นพบ {len(rows)} แถวในตาราง กำลังค้นหาสถานี 'อินทร์บุรี'...")

        # วนลูปเพื่อหาแถวที่มีข้อมูลของสถานีอินทร์บุรี
        for row in rows:
            # ค้นหาเซลล์หัวเรื่อง (th) ที่มีข้อความ "อินทร์บุรี"
            station_header = row.find("th")
            if station_header and "อินทร์บุรี" in station_header.get_text(strip=True):
                print("✅ พบข้อมูลของ 'อินทร์บุรี'")

                # ดึงเซลล์ข้อมูล (td) ทั้งหมดในแถวนั้น
                tds = row.find_all("td")

                # จากโครงสร้าง HTML ที่ให้มา:
                # tds[0] คือ ที่ตั้ง (ต.อินทร์บุรี)
                # tds[1] คือ ระดับน้ำ (9.03)
                if len(tds) > 1 and tds[1].text.strip():
                    level_str = tds[1].text.strip()
                    water_level = float(level_str)
                    print(f"ระดับน้ำอินทร์บุรีที่ดึงได้ = {water_level} ม.รทก.")
                    return water_level
                else:
                    print("⚠️ พบแถว 'อินทร์บุรี' แต่ข้อมูลระดับน้ำในคอลัมน์ที่ 2 ไม่ถูกต้อง")
                    return None # คืนค่า None เมื่อข้อมูลไม่สมบูรณ์

        print("❌ ไม่พบข้อมูลของ 'อินทร์บุรี' ในหน้าเว็บหลังจากการค้นหาทุกแถว")
        return None

    except requests.exceptions.RequestException as e:
        print(f"เกิดข้อผิดพลาดในการเชื่อมต่อเครือข่าย: {e}")
        return None
    except Exception as e:
        print(f"เกิดข้อผิดพลาดที่ไม่คาดคิดในการดึงข้อมูล: {e}")
        return None

def get_dam_discharge_from_file():
    """
    อ่านข้อมูลการระบายน้ำของเขื่อนจากไฟล์ (ถ้ามี)
    """
    try:
        print("กำลังอ่านข้อมูลเขื่อนจากไฟล์ dam_data.txt...")
        with open('dam_data.txt', 'r') as f:
            discharge_rate = float(f.read().strip())
        print(f"เขื่อนระบายน้ำ {discharge_rate:,.0f} ลบ.ม./วินาที")
        return discharge_rate
    except FileNotFoundError:
        # หากไม่พบไฟล์ จะใช้ค่า default ตามที่เคยตั้งไว้ใน Log
        print("⚠️ ไม่พบไฟล์ dam_data.txt! ใช้ค่า default = 1000 ลบ.ม./วินาที")
        return 1000
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการอ่านไฟล์ dam_data.txt: {e}")
        return 1000 # กรณีเกิดปัญหาอื่น ให้ใช้ค่า default

def analyze_and_create_message(inburi_level, dam_discharge):
    """
    วิเคราะห์ข้อมูลและสร้างข้อความสำหรับส่งแจ้งเตือน
    """
    if inburi_level is None:
        return "เกิดข้อผิดพลาด: ไม่สามารถดึงข้อมูลระดับน้ำอินทร์บุรีได้ กรุณาตรวจสอบเว็บไซต์ singburi.thaiwater.net หรือตรวจสอบ Log การทำงานล่าสุด"

    # ค่าความสูงตลิ่ง (อาจปรับเปลี่ยนได้ตามข้อมูลจริง)
    bank_height = 13.0
    distance_to_bank = bank_height - inburi_level

    # --- กำหนดเกณฑ์การแจ้งเตือน ---
    if dam_discharge > 2400 or distance_to_bank < 1.0:
        status_emoji = "🟥"
        status_title = "‼️ ประกาศเตือนภัยระดับสูงสุด ‼️"
        recommendation = """คำแนะนำ:
1. เตรียมพร้อมอพยพหากอยู่ในพื้นที่เสี่ยง
2. ขนย้ายทรัพย์สินขึ้นที่สูงโดยด่วน
3. งดใช้เส้นทางสัญจรริมแม่น้ำ"""
    elif dam_discharge > 1800 or distance_to_bank < 2.0:
        status_emoji = "🟨"
        status_title = "‼️ ประกาศเฝ้าระวัง ‼️"
        recommendation = """คำแนะนำ:
1. บ้านเรือนริมตลิ่งนอกคันกั้นน้ำ ให้เริ่มขนของขึ้นที่สูง
2. ติดตามสถานการณ์อย่างใกล้ชิด"""
    else:
        status_emoji = "🟩"
        status_title = "สถานะปกติ"
        recommendation = "สถานการณ์น้ำยังปกติ ใช้ชีวิตได้ตามปกติครับ"

    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)

    message = (
        f"{status_emoji} {status_title}\n"
        f"รายงานสถานการณ์น้ำเจ้าพระยา อ.อินทร์บุรี\n"
        f"ประจำวันที่: {now.strftime('%d/%m/%Y %H:%M')} น.\n\n"
        f"• ระดับน้ำ (อินทร์บุรี): {inburi_level:.2f} ม.รทก.\n"
        f"  (ต่ำกว่าตลิ่งประมาณ {distance_to_bank:.2f} ม.)\n"
        f"• เขื่อนเจ้าพระยา (ข้อมูลอ้างอิง): {dam_discharge:,.0f} ลบ.ม./วินาที\n\n"
        f"{recommendation}"
    )
    return message

def send_line_broadcast(message):
    """
    ส่งข้อความแจ้งเตือนไปยัง LINE
    """
    if not LINE_TOKEN:
        print("❌ ไม่พบ LINE_CHANNEL_ACCESS_TOKEN ใน Environment Variables!")
        return
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": message}]}
    try:
        response = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ ส่งข้อความ Broadcast สำเร็จ!")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการส่ง LINE Broadcast: {e}")

# --- ส่วนหลักของการทำงาน ---
if __name__ == "__main__":
    print("===== เริ่มการทำงานของระบบเฝ้าระวังน้ำ v6.0 (Optimized Scraper) =====")
    inburi_level = get_singburi_data(SINGBURI_WATER_URL)
    dam_discharge = get_dam_discharge_from_file()
    final_message = analyze_and_create_message(inburi_level, dam_discharge)
    print("\n--- ข้อความที่จะส่ง ---")
    print(final_message)
    print("-------------------------\n")
    send_line_broadcast(final_message)
    print("===== การทำงานเสร็จสิ้น =====")
