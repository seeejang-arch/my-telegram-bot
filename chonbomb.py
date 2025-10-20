import hashlib
import asyncio
import logging
import mysql.connector
import random
from datetime import datetime
import qrcode
import io
from datetime import date
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ================== HÀM MÃ HÓA MẬT KHẨU ==================
def hash_pw(pw):
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest()
# ================== CONFIG ==================
BOT_TOKEN = "8030166292:AAFOdhLjHMYAMKRpBmc97niaZjfKMVhkPpw"
ADMIN_ID = 7994279488
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "tinhlene1231",
    "database": "oknha12_bot"
}
users = {} 
rut_mo = False  # bật tắt rút tiền
ma_giao_dich = f"{random.randint(0, 999999):06}"
joined_all = False  # ← đổi thành True để test


def get_db():
    conn = mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"]
    )
    print("✅ Đang kết nối đến database:", conn.database)
    return conn

# ================== DB ==================
def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def create_tables():
    db = get_db()
    c = db.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT PRIMARY KEY,
        username VARCHAR(255),
        password VARCHAR(64),
        created_at DATETIME,
        failed_attempts INT DEFAULT 0,
        locked TINYINT DEFAULT 0,
        balance BIGINT DEFAULT 0,
        total_deposit BIGINT DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS invites (
        inviter_id BIGINT,
        invitee_id BIGINT PRIMARY KEY,
        reward BIGINT DEFAULT 0,
        valid TINYINT DEFAULT 0
    )
    """)
    db.commit()
    db.close()

def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ================== INVITE HELPERS ==================
def add_invite(inviter_id, invitee_id):
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT IGNORE INTO invites (inviter_id, invitee_id) VALUES (%s,%s)", (inviter_id, invitee_id))
        db.commit()
    finally:
        db.close()

def check_invite_valid(user_id, tong_nap):
    """Kiểm tra nếu user_id đã nạp ≥ 50k thì đánh dấu hợp lệ cho inviter"""
    if tong_nap < 50000:
        return None, None

    db = get_db()
    c = db.cursor()
    c.execute("SELECT inviter_id FROM invites WHERE invitee_id=%s AND valid=0", (user_id,))
    row = c.fetchone()
    if not row:
        db.close()
        return None, None

    inviter_id = row[0]
    reward = random.randint(2000, 22222)

    c.execute("UPDATE invites SET valid=1, reward=%s WHERE invitee_id=%s", (reward, user_id))
    c.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (reward, inviter_id))
    db.commit()
    db.close()

    return inviter_id, reward
#==============THỜI GIAN ĐĂNG NHẬP===============
def is_logged_in_recently(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT last_login FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if not row or not row[0]:
        return False

    # ⏱ Cho phép hoạt động trong vòng 10 phút (600 giây)
    return (datetime.now() - row[0]).total_seconds() <= 600

# ================== MENUS ==================
def start_menu():
    kb = [
        [InlineKeyboardButton("🆕 Tạo tài khoản", callback_data="create_acc")],
        [InlineKeyboardButton("🔑 Đăng nhập", callback_data="login_menu")],
        [InlineKeyboardButton("🔁 Đổi mật khẩu", callback_data="change_pw")]
    ]
    return InlineKeyboardMarkup(kb)


def persistent_menu(user_id=None):
    kb = [
        [KeyboardButton("ℹ️ Thông tin"), KeyboardButton("🤝 Mời bạn bè")],
        [KeyboardButton("💳 Nạp tiền"), KeyboardButton("🏦 Rút tiền")],
        [KeyboardButton("📌 Nhiệm vụ"), KeyboardButton("🎰 Quay Slot")],
        [KeyboardButton("📢 Thông báo")]
    ]

    # ✅ Chỉ hiển thị nút thống kê nếu là admin
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton("📊 Thống kê")])

    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def confirm_cancel_menu():
    kb = [
        [InlineKeyboardButton("✅ Xác nhận", callback_data="confirm_acc")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_acc")]
    ]
    return InlineKeyboardMarkup(kb)

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        try:
            inviter_id = int(args[0])
            invitee_id = update.effective_user.id
            if inviter_id != invitee_id:
                add_invite(inviter_id, invitee_id)
        except:
            pass
    await update.message.reply_text(
        "👋 Chào mừng!\nHãy chọn bên dưới:",
        reply_markup=start_menu()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "create_acc":
        await query.edit_message_text(
            "🆕 Dùng lệnh sau để tạo tài khoản:\n\n"
            "`/creatacc <mật khẩu> <mật khẩu>`\n\n"
            "⚠️ Mật khẩu 6–20 ký tự.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data="back")]])
        )
    elif data == "login_menu":
        await query.edit_message_text(
            "🔑 Dùng lệnh để đăng nhập:\n\n"
            "`/login <mật khẩu>`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data="back")]])
        )
    elif data == "back":
        await query.edit_message_text("👋 Chào mừng!\nHãy chọn bên dưới:", reply_markup=start_menu())
    elif data == "change_pw":
        await query.edit_message_text(
        "🔁 Để đổi mật khẩu, dùng lệnh:\n\n"
        "`/doimatkhau <mật khẩu cũ> <mật khẩu mới> <nhập lại>`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data="back")]])
       )


async def creatacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    args = context.args

    if len(args) != 2:
        await update.message.reply_text("❌ Sai cú pháp.\nDùng: `/creatacc <mật khẩu> <mật khẩu>`", parse_mode="Markdown")
        return

    pw1, pw2 = args
    if pw1 != pw2 or not (6 <= len(pw1) <= 20):
        await update.message.reply_text("❌ Mật khẩu không hợp lệ hoặc không khớp.")
        return

    # ✅ Kiểm tra nếu đã có tài khoản
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id FROM users WHERE id=%s", (tg_id,))
    if c.fetchone():
        await update.message.reply_text(
            "⚠️ Bạn đã đăng ký tài khoản trước đó.\nKhông thể tạo lại lần thứ hai.",
            parse_mode="Markdown"
        )
        db.close()
        return

    db.close()

    context.user_data["temp_pw"] = hash_pw(pw1)
    await update.message.delete()
    await update.message.reply_text("Xác nhận tạo tài khoản?", reply_markup=confirm_cancel_menu())


async def confirm_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tg_id = query.from_user.id
    pw = context.user_data.get("temp_pw")
    if not pw:
        return

    db = get_db()
    c = db.cursor()

    # ✅ Kiểm tra lại lần nữa để tránh lỗi race condition
    c.execute("SELECT id FROM users WHERE id=%s", (tg_id,))
    if c.fetchone():
        await query.edit_message_text("⚠️ Bạn đã có tài khoản. Không thể tạo lại.", parse_mode="Markdown")
        db.close()
        return

    c.execute("""
        INSERT INTO users (id, username, password, created_at, failed_attempts, locked, balance, total_deposit)
        VALUES (%s, %s, %s, %s, 0, 0, 0, 0)
    """, (tg_id, query.from_user.username, pw, datetime.now()))
    db.commit()
    db.close()

    await query.edit_message_text(
        "✅ Tạo tài khoản thành công!\nĐăng nhập bằng: `/login <mật khẩu>`",
        parse_mode="Markdown"
    )
    context.user_data.pop("temp_pw", None)


async def cancel_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data.pop("temp_pw", None)
    await query.edit_message_text("👋 Quay lại menu:", reply_markup=start_menu())

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Sai cú pháp.\nDùng: `/login <mật khẩu>`", parse_mode="Markdown")
        return
    pw = hash_pw(args[0])

    db = get_db()
    c = db.cursor()
    c.execute("SELECT password,failed_attempts,locked FROM users WHERE id=%s", (tg_id,))
    row = c.fetchone()
    await update.message.delete()

    if not row:
        await update.message.reply_text("❌ Bạn chưa có tài khoản.")
        db.close()
        return

    real_pw, failed, locked = row
    if locked:
        await update.message.reply_text("🔒 Tài khoản bị khóa. Liên hệ admin.")
        db.close()
        return

    if pw == real_pw:
        c.execute("UPDATE users SET failed_attempts=0, username=%s, last_login=%s WHERE id=%s",
          (update.effective_user.username, datetime.now(), tg_id))
        db.commit()
        await update.message.reply_text("✅ Đăng nhập thành công!", reply_markup=persistent_menu())
    else:
        failed += 1
        if failed >= 5:
            c.execute("UPDATE users SET locked=1 WHERE id=%s", (tg_id,))
            await update.message.reply_text("🔒 Sai mật khẩu 5 lần. Tài khoản bị khóa.")
        else:
            c.execute("UPDATE users SET failed_attempts=%s WHERE id=%s", (failed, tg_id))
            await update.message.reply_text(f"❌ Sai mật khẩu. Thử lại ({failed}/5)")
        db.commit()
    db.close()
async def doimatkhau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("❌ Sai cú pháp.\nDùng: `/doimatkhau <mật khẩu cũ> <mới> <nhập lại>`", parse_mode="Markdown")
        return

    old, new1, new2 = args
    if new1 != new2 or not (6 <= len(new1) <= 20):
        await update.message.reply_text("❌ Mật khẩu mới không hợp lệ hoặc không khớp.")
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT password FROM users WHERE id=%s", (tg_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("❌ Bạn chưa có tài khoản.")
        db.close()
        return

    if hash_pw(old) != row[0]:
        await update.message.reply_text("❌ Mật khẩu cũ không đúng.")
        db.close()
        return

    new_pw = hash_pw(new1)
    c.execute("UPDATE users SET password=%s WHERE id=%s", (new_pw, tg_id))
    c.execute("INSERT INTO password_history (user_id, password) VALUES (%s, %s)", (tg_id, new_pw))
    db.commit()
    db.close()
    await update.message.reply_text("✅ Đổi mật khẩu thành công.")
async def setpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền dùng lệnh này.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ Dùng: `/setpass <id> <mật khẩu>`", parse_mode="Markdown")
        return

    try:
        uid = int(args[0])
        raw_pw = args[1]
        if not (6 <= len(raw_pw) <= 20):
            await update.message.reply_text("❌ Mật khẩu phải từ 6–20 ký tự.")
            return
    except:
        await update.message.reply_text("❌ Dữ liệu không hợp lệ.")
        return

    new_pw = hash_pw(raw_pw)
    db = get_db()
    c = db.cursor()

    # Kiểm tra người dùng
    c.execute("SELECT username FROM users WHERE id=%s", (uid,))
    user = c.fetchone()
    if not user:
        await update.message.reply_text("❌ Không tìm thấy người dùng.")
        db.close()
        return

    username = user[0] or "Không có"

    # Cập nhật mật khẩu
    c.execute("UPDATE users SET password=%s WHERE id=%s", (new_pw, uid))
    c.execute("INSERT INTO password_history (user_id, password) VALUES (%s, %s)", (uid, new_pw))
    db.commit()

    # Lấy thời gian tạo mật khẩu mới
    c.execute("SELECT changed_at FROM password_history WHERE user_id=%s ORDER BY changed_at DESC LIMIT 1", (uid,))
    time_row = c.fetchone()
    db.close()

    time_str = time_row[0].strftime("%d/%m/%Y %H:%M") if time_row else "Không rõ"

    # Soạn tin nhắn
    text = (
        f"👤 Username: @{username}\n"
        f"🆔 ID: {uid}\n"
        f"🔐 Mật khẩu hiện tại: `{new_pw[:12]}...`\n"
        f"📅 Thời gian tạo: {time_str}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


def is_logged_in_recently(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT last_login FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if not row or not row[0]:
        return False

    return (datetime.now() - row[0]).total_seconds() <= 600

# ================== INFO ==================
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id

    if not is_logged_in_recently(tg_id):
        await update.message.reply_text(
        "⏳ *Phiên đăng nhập đã hết hạn do bạn không hoạt động trong 10 phút.*\n\n"
        "🔐 Vui lòng đăng nhập lại bằng lệnh:\n`/login <mật khẩu>`",
        parse_mode="Markdown"
    )
        return


    db = get_db()
    c = db.cursor()
    c.execute("SELECT created_at, balance, username FROM users WHERE id=%s", (tg_id,))
    row = c.fetchone()
    db.close()

    if row:
        created_at, balance, username_db = row
        days = (datetime.now() - created_at).days if created_at else 0
        username = update.effective_user.username or username_db or "❌ Chưa có"
        await update.message.reply_text(
            f"👤 Tên: {update.effective_user.full_name}\n"
            f"🏷️ Username: @{username}\n"
            f"🆔 ID: {tg_id}\n"
            f"💰 Số dư: {balance:,.0f} đ\n"
            f"📅 Ngày đăng ký: {days} ngày trước"
        )
    else:
        await update.message.reply_text("❌ Bạn chưa có tài khoản.")

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    db = get_db()
    c = db.cursor()
    c.execute("SELECT COUNT(*), SUM(valid), COALESCE(SUM(reward),0) FROM invites WHERE inviter_id=%s", (tg_id,))
    total, valid_count, total_reward = c.fetchone()
    db.close()

    await update.message.reply_text(
        f"🤝 Mời bạn bè bằng link sau:\n"
        f"https://t.me/{context.bot.username}?start={tg_id}\n\n"
        f"👥 Tổng mời: {total}\n"
        f"✅ Hợp lệ: {valid_count or 0}\n"
        f"💰 Hoa hồng: {total_reward:,} đ"
    )

async def mokhoa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Dùng: /mokhoa <id>")
        return
    uid = int(args[0])
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE users SET locked=0,failed_attempts=0 WHERE id=%s", (uid,))
    db.commit()
    db.close()
    await update.message.reply_text(f"✅ Đã mở khóa cho {uid}")

# ================== LỆNH ADMIN NẠP TIỀN ==================
async def admin_naptien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Bạn không có quyền dùng lệnh này.")

    if len(context.args) < 2:
        return await update.message.reply_text("⚠️ Cú pháp: /naptien <id> <số tiền>")

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except:
        return await update.message.reply_text("❌ ID hoặc số tiền không hợp lệ.")

    conn = get_db()
    cursor = conn.cursor()

    # Cộng tiền vào balance và total_deposit
    cursor.execute("UPDATE users SET balance = balance + %s, total_deposit = total_deposit + %s WHERE id=%s", (amount, amount, user_id))
    conn.commit()

    # Lấy số dư hiện tại
    cursor.execute("SELECT balance, total_deposit FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    balance, tong_nap = row if row else (0, 0)

    cursor.close()
    conn.close()

    # Thông báo cho user
    try:
        await context.bot.send_message(user_id, f"💳 Tài khoản của bạn đã được nạp {amount:,}đ.\n💰 Số dư hiện tại: {balance:,}đ")
    except:
        pass

    await update.message.reply_text(f"✅ Đã nạp {amount:,}đ cho user {user_id}")

    # Check invite hợp lệ
    inviter_id, reward = check_invite_valid(user_id, tong_nap)
    if inviter_id:
        await context.bot.send_message(inviter_id, f"🎉 Bạn đã mời {user_id} hợp lệ và nhận {reward:,}đ!")

# ================== LỆNH ADMIN TRỪ TIỀN ==================
async def admin_trutien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Bạn không có quyền dùng lệnh này.")

    if len(context.args) < 3:
        return await update.message.reply_text("⚠️ Cú pháp: /trutien <id> <số tiền> <lời nhắn>")

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        reason = " ".join(context.args[2:])
    except:
        return await update.message.reply_text("❌ ID hoặc số tiền không hợp lệ.")

    conn = get_db()
    cursor = conn.cursor()

    # Trừ tiền trong balance
    cursor.execute("UPDATE users SET balance = balance - %s WHERE id=%s", (amount, user_id))
    conn.commit()

    # Lấy số dư hiện tại
    cursor.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    cursor.close()
    conn.close()

    # Thông báo cho user
    try:
        await context.bot.send_message(user_id, f"💸 Tài khoản của bạn đã bị trừ {amount:,}đ.\n📌 Lý do: {reason}\n💰 Số dư còn lại: {balance:,}đ")
    except:
        pass

    await update.message.reply_text(f"✅ Đã trừ {amount:,}đ của user {user_id} (Lý do: {reason})")
# ================== HANDLER RÚT TIỀN ==================
async def rut_tien_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏦 Vui lòng thực hiện theo hướng dẫn sau:\n\n"
        "👉 /rutbank <số tiền> <mã ngân hàng> <số tài khoản> <tên chủ tài khoản>\n\n"
        "📌 Ví dụ:\n"
        "/rutbank 100000 VCB 0123456789 NGUYEN VAN A\n\n"
        "⚠️ Lưu ý:\n"
        "- Rút tối thiểu 100,000đ\n"
        "- Tân thủ chỉ rút tối đa 100,000đ (sau khi nạp mở khoá rút tối đa 10,000,000đ)\n"
        "- Phải có ít nhất 1 giao dịch nạp mới được rút\n"
        "- Không hỗ trợ hoàn tiền nếu nhập sai thông tin\n\n"
        "📋 MÃ NGÂN HÀNG:\n"
        "🔹 VCB = Vietcombank\n"
        "🔹 ACB = NH TMCP Á Châu\n"
        "🔹 BIDV = NH Đầu tư & Phát triển VN\n"
        "🔹 MBB = MB Bank\n"
        "🔹 MSB = Maritime Bank\n"
        "🔹 TCB = Techcombank\n"
        "..."
    )
    await update.message.reply_text(text)
# ================= LỆNH RÚT TIỀN =================
async def rutbank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    if len(args) < 4:
        await update.message.reply_text(
            "❌ Sai cú pháp!\nVui lòng nhập theo mẫu:\n"
            "`/rutbank <Mã NH> <Số tiền> <Số TK> <Tên chủ TK>`",
            parse_mode="Markdown"
        )
        return

    bank_code = args[0].upper()
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    account_number = args[2]
    account_name = " ".join(args[3:]).upper()

    # Lấy thông tin user
    user = users.get(user_id, {"balance": 0, "nap": 0})
    balance = user["balance"]
    nap = user["nap"]  # số lần nạp

    # Kiểm tra điều kiện tân thủ
    if nap == 0:
        if amount != 100000:
            await update.message.reply_text("❌ Tân thủ chỉ có thể rút đúng 100,000đ.")
            return
    else:
        if amount < 100000 or amount > 10000000:
            await update.message.reply_text("❌ Số tiền rút phải từ 100,000đ đến 10,000,000đ.")
            return

    if amount > balance:
        await update.message.reply_text("❌ Số dư không đủ để rút.")
        return

    # Hiện thông tin + nút xác nhận
    text = (
        f"📤 Yêu cầu rút tiền\n\n"
        f"🏦 Ngân hàng: {bank_code}\n"
        f"💰 Số tiền: {amount:,}đ\n"
        f"🔢 Số TK: {account_number}\n"
        f"👤 Chủ TK: {account_name}\n\n"
        f"👉 Bạn có xác nhận giao dịch này không?"
    )
    kb = [
        [InlineKeyboardButton("✅ Xác nhận", callback_data=f"confirm_rut|{user_id}|{bank_code}|{amount}|{account_number}|{account_name}")],
        [InlineKeyboardButton("❌ Hủy", callback_data=f"cancel_rut|{user_id}")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))


# ================= XỬ LÝ CALLBACK =================
async def rutbank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    action = data[0]
    user_id = int(data[1])

    if action == "cancel_rut":
        await query.edit_message_text("❌ Giao dịch rút tiền đã bị hủy.")
        return

    if action == "confirm_rut":
        bank_code, amount, account_number, account_name = data[2], int(data[3]), data[4], data[5]

        # Trừ tiền user
        users[user_id]["balance"] -= amount
        save_users()

        # Gửi thông tin cho admin
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Yêu cầu rút tiền mới:\n\n"
            f"👤 User ID: {user_id}\n"
            f"🏦 Ngân hàng: {bank_code}\n"
            f"💰 Số tiền: {amount:,}đ\n"
            f"🔢 Số TK: {account_number}\n"
            f"👤 Chủ TK: {account_name}"
        )

        await query.edit_message_text("✅ Yêu cầu rút tiền đã được gửi đến admin, vui lòng chờ xử lý.")
# ================== HÀM LẤY SỐ DƯ ==================
def get_balance(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    db.close()
    return result[0] if result else 0
#===================TẮT BẬT RÚT TIỀN=======================
async def morut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global rut_mo
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    rut_mo = True

    await update.message.reply_text("✅ Đã mở chức năng rút tiền.")
async def tatrut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global rut_mo
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    rut_mo = False
    await update.message.reply_text("⚠️ Chức năng rút tiền đang được bảo trì.")

# ================== LỆNH RÚT TIỀN ==================
async def rutbank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global rut_mo
    user_id = update.effective_user.id
    args = context.args

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    # ✅ Kiểm tra trạng thái bảo trì
    if not rut_mo:
        await update.message.reply_text("⚠️ Chức năng rút tiền đang bảo trì. Vui lòng thử lại sau.")
        return

    # ✅ Kiểm tra cú pháp
    if len(args) < 4:
        await update.message.reply_text("❌ Sai cú pháp.\n\nVí dụ: /rutbank 100000 VCB 0123456789 NGUYEN VAN A")
        return

    # ✅ Kiểm tra số tiền
    try:
        amount = int(args[0])
    except:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    bank_code = args[1].upper()
    stk = args[2]
    name = " ".join(args[3:]).upper()

    if amount < 100000:
        await update.message.reply_text("❌ Rút tối thiểu 100,000đ.")
        return

    if amount > 10000000:
        await update.message.reply_text("❌ Rút tối đa 10,000,000đ.")
        return

    # ✅ Kiểm tra số dư
    balance = get_balance(user_id)
    if balance < amount:
        await update.message.reply_text("❌ Số dư không đủ.")
        return

    # ✅ Hiển thị xác nhận
    text = (
        f"📋 *Xác nhận rút tiền:*\n\n"
        f"👤 ID: `{user_id}`\n"
        f"💰 Số tiền: *{amount:,}đ*\n"
        f"🏦 Ngân hàng: *{bank_code}*\n"
        f"🔢 STK: `{stk}`\n"
        f"👤 Chủ TK: *{name}*\n\n"
        "👉 Bạn có muốn xác nhận giao dịch này không?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Xác nhận", callback_data=f"confirm_rut_{user_id}_{amount}_{bank_code}_{stk}_{name}"),
            InlineKeyboardButton("❌ Huỷ", callback_data=f"cancel_rut_{user_id}")
        ]
    ]

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ================== CALLBACK NGƯỜI DÙNG ==================
async def rutbank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()


    data = query.data.split("_")
    action = data[0]
    command = data[1]

    if action == "cancel":
        await query.edit_message_text("❌ Bạn đã huỷ yêu cầu rút tiền.")
        return

    if action == "confirm":
        if len(data) < 7:
            await query.message.reply_text("❌ Dữ liệu xác nhận không hợp lệ.")
            return

        try:
            user_id = int(data[2])
            amount = int(data[3])
            bank_code = data[4]
            stk = data[5]
            name = "_".join(data[6:])
        except:
            await query.message.reply_text("❌ Dữ liệu xác nhận không hợp lệ.")
            return

        balance = get_balance(user_id)
        if balance < amount:
            await query.message.reply_text("❌ Số dư không đủ để thực hiện giao dịch.")
            return

        ma_giao_dich = f"{random.randint(0, 999999):06}"

        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, user_id))
        cursor.execute(
            "INSERT INTO withdraws (user_id, amount, bank_code, stk, name, ma_giao_dich, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, amount, bank_code, stk, name, ma_giao_dich, "pending")
        )
        db.commit()
        db.close()

        await query.edit_message_text(
            f"✅ Yêu cầu rút {amount:,}đ tới tài khoản {stk} ({bank_code}) đã được ghi nhận.\n"
            f"💳 Chủ tài khoản: {name}\n"
            f"⏳ Vui lòng chờ xử lý trong vòng 24h.\n"
            f"🔖 Mã giao dịch: `{ma_giao_dich}`",
            parse_mode="Markdown"
        )

        admin_text = (
            f"📥 Yêu cầu rút tiền từ người dùng:\n\n"
            f"👤 ID: {user_id}\n"
            f"💰 Số tiền: {amount:,}đ\n"
            f"🏦 Ngân hàng: {bank_code}\n"
            f"🔢 STK: {stk}\n"
            f"👤 Chủ TK: {name}\n"
            f"🔖 Mã giao dịch: `{ma_giao_dich}`\n\n"
            "Chọn hành động:"
        )

        admin_keyboard = [
            [
                InlineKeyboardButton("✅ Chuyển khoản", callback_data=f"admin_chuyen_{user_id}_{amount}_{ma_giao_dich}"),
                InlineKeyboardButton("❌ Hoàn tiền", callback_data=f"admin_hoan_{user_id}_{amount}_{ma_giao_dich}")
            ]
        ]

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )


# ================== CALLBACK ADMIN ==================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    if len(data) < 5:
        await query.message.reply_text("❌ Dữ liệu không hợp lệ.")
        return

    action = data[1]
    user_id = int(data[2])
    amount = int(data[3])
    ma_giao_dich = data[4]

    db = get_db()
    cursor = db.cursor()

    if action == "chuyen":
        cursor.execute("UPDATE withdraws SET status = 'done' WHERE ma_giao_dich = %s", (ma_giao_dich,))
        db.commit()
        db.close()

        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Bạn đã rút thành công số tiền {amount:,}đ ^.^"
        )
        await query.edit_message_text(
            text=f"✅ Đã xác nhận chuyển khoản cho người dùng {user_id} - {amount:,}đ"
        )

    elif action == "hoan":
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
        cursor.execute("UPDATE withdraws SET status = 'hoan' WHERE ma_giao_dich = %s", (ma_giao_dich,))
        db.commit()
        db.close()

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ Đơn rút tiền của bạn đã bị hoàn trả {amount:,}đ.\n"
                "Vui lòng tạo lại đơn mới hoặc liên hệ admin để biết chi tiết."
            )
        )
        await query.edit_message_text(
            text=f"❌ Đã hoàn tiền cho người dùng {user_id} - {amount:,}đ"
        )

#===================LỆNH TRA GIAO DỊCH RÚT===============
async def tragiaodich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Vui lòng nhập đúng mã giao dịch.\nVí dụ: /tragiaodich 123456")
        return

    ma_giao_dich = args[0]

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT user_id, amount, bank_code, stk, name, created_at, status FROM withdraws WHERE ma_giao_dich = %s",
        (ma_giao_dich,)
    )
    result = cursor.fetchone()
    db.close()

    if not result:
        await update.message.reply_text("❌ Không tìm thấy giao dịch với mã này.")
        return

    user_id, amount, bank_code, stk, name, created_at, status = result

    # Xác định trạng thái
    if status == "done":
        trang_thai = "✅ Đã chuyển khoản"
    elif status == "hoan":
        trang_thai = "❌ Hoàn tiền"
    else:
        trang_thai = "⏳ Đang chờ xử lý"

    text = (
        f"📥 Yêu cầu rút tiền từ người dùng:\n\n"
        f"👤 ID: {user_id}\n"
        f"💰 Số tiền: {amount:,}đ\n"
        f"🏦 Ngân hàng: {bank_code}\n"
        f"🔢 STK: {stk}\n"
        f"👤 Chủ TK: {name}\n"
        f"🔖 Mã giao dịch: `{ma_giao_dich}`\n"
        f"🕒 Thời gian tạo: `{created_at.strftime('%d/%m/%Y %H:%M:%S')}`\n"
        f"{trang_thai}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")
#========XỬ LÝ NÚT NẠP TIỀN=================
# ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban
async def xu_ly_nap_tien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💳 Hướng dẫn nạp tiền:\n\n"
        "🔹 /bank <số tiền> — Nạp qua ngân hàng (tối thiểu 20,000đ)\n"
        "🔹 /napthe <tên thẻ> <seri> <mã thẻ> <số tiền>\n"
        "    ➤ Tên thẻ: viettel, vina, mobi\n"
        "    ➤ Phí: 10% số tiền\n\n"
        "📌 Ví dụ số tiền nhận được sau khi trừ phí:\n"
        "• Nạp 10,000đ → Nhận 9,000đ\n"
        "• Nạp 20,000đ → Nhận 18,000đ\n"
        "• Nạp 50,000đ → Nhận 45,000đ\n"
        "• Nạp 100,000đ → Nhận 90,000đ\n"
        "• Nạp 200,000đ → Nhận 180,000đ\n"
        "• Nạp 500,000đ → Nhận 450,000đ\n\n"
        "🔸 /napbank <số tiền> — Hiển thị mã QR và nội dung chuyển khoản (hiệu lực 5 phút)\n"
        "🔸 /momo <số tiền> — Hiển thị mã QR và nội dung chuyển tiền (hiệu lực 5 phút)\n"
    )
    await update.message.reply_text(text)

#===============NẠP TIỀN======================
async def nap_tien_huong_dan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id  # ✅ Khai báo user_id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    text = (
        "💳 *Hướng dẫn nạp tiền:*\n\n"
        "🔹 `/bank <số tiền>` — Nạp qua ngân hàng (tối thiểu 20,000đ)\n"
        "🔹 `/napthe <tên thẻ> <seri> <mã thẻ> <số tiền>`\n"
        "    ➤ Tên thẻ: viettel, vina, mobi\n"
        "    ➤ Phí: 10% số tiền\n\n"
        "📌 *Ví dụ số tiền nhận được sau khi trừ phí:*\n"
        "• Nạp 10,000đ → Nhận 9,000đ\n"
        "• Nạp 20,000đ → Nhận 18,000đ\n"
        "• Nạp 50,000đ → Nhận 45,000đ\n"
        "• Nạp 100,000đ → Nhận 90,000đ\n"
        "• Nạp 200,000đ → Nhận 180,000đ\n"
        "• Nạp 500,000đ → Nhận 450,000đ\n\n"
        "🔸 `/napbank <số tiền>` — Hiển thị mã QR và nội dung chuyển khoản (hiệu lực 5 phút)\n"
        "🔸 `/momo <số tiền>` — Hiển thị mã QR và nội dung chuyển tiền (hiệu lực 5 phút)"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def napthe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "❌ Sai cú pháp.\n\nVí dụ: /napthe viettel 123456789 987654321 100000"
        )
        return

    telco = args[0].lower()
    seri = args[1]
    code = args[2]

    try:
        amount = int(args[3])
    except:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    if telco not in ["viettel", "vina", "mobi"]:
        await update.message.reply_text("❌ Tên thẻ không hợp lệ. Chỉ hỗ trợ viettel, vina, mobi.")
        return

    if amount < 10000:
        await update.message.reply_text("❌ Mệnh giá tối thiểu là 10,000đ.")
        return

    net_amount = int(amount * 0.9)
    note = f"{telco}-{seri}-{code}"

    # Lưu giao dịch
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO deposits (user_id, amount, method, note) VALUES (%s, %s, %s, %s)",
        (update.effective_user.id, net_amount, "thecao", note)
    )
    db.commit()
    db.close()

    # Gửi xác nhận + nút
    keyboard = [
        [InlineKeyboardButton("📤 Chuyển thẻ", callback_data=f"chuyen_{note}")],
        [InlineKeyboardButton("✏️ Sửa mã thẻ", callback_data="sua_thecao")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📥 Đã nhận thông tin thẻ cào:\n\n"
        f"🔸 Nhà mạng: {telco.upper()}\n"
        f"🔢 Seri: `{seri}`\n"
        f"🔑 Mã thẻ: `{code}`\n"
        f"💰 Mệnh giá: {amount:,}đ\n"
        f"💸 Số tiền nhận sau phí (10%): {net_amount:,}đ\n\n"
        "⏳ Vui lòng bấm *Chuyển thẻ* để gửi cho admin xử lý.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
async def xu_ly_thecao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("chuyen_"):
        note = data.replace("chuyen_", "")

        # Lấy thông tin giao dịch
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id, amount FROM deposits WHERE note = %s", (note,))
        result = cursor.fetchone()
        db.close()

        if not result:
            await query.message.reply_text("❌ Không tìm thấy giao dịch.")
            return

        user_id, amount = result

        # Gửi cho admin
        keyboard = [
            [InlineKeyboardButton("✅ Cộng tiền", callback_data=f"cong_{note}")],
            [InlineKeyboardButton("❌ Hoàn", callback_data=f"hoan_{note}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📨 Yêu cầu xử lý thẻ cào:\n\n"
                f"👤 ID: `{user_id}`\n"
                f"💰 Số tiền: `{amount:,}đ`\n"
                f"📝 Mã thẻ: `{note}`"
            ),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        await query.message.reply_text("✅ Đã chuyển thẻ cho admin xử lý.")

    elif data == "sua_thecao":
        await query.message.reply_text("✏️ Vui lòng nhập lại thông tin thẻ bằng lệnh /napthe.")
async def xu_ly_admin_thecao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("cong_") or data.startswith("hoan_"):
        note = data.split("_", 1)[1]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id, amount FROM deposits WHERE note = %s", (note,))
        result = cursor.fetchone()

        if not result:
            await query.message.reply_text("❌ Không tìm thấy giao dịch.")
            db.close()
            return

        user_id, amount = result

        if data.startswith("cong_"):
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
            cursor.execute("UPDATE deposits SET status = 'done' WHERE note = %s", (note,))
            db.commit()
            db.close()

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Bạn đã nạp thẻ cào thành công {amount:,}đ."
            )

            await query.message.reply_text("✅ Đã cộng tiền cho người dùng.")

        elif data.startswith("hoan_"):
            db.close()
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Mã thẻ của bạn đã sai hoặc gặp lỗi. Vui lòng thao tác lại."
            )
            await query.message.reply_text("❌ Đã hoàn giao dịch.")

def generate_transfer_note():
    prefix = random.choice(["taxi", "chuyen khoang", "mua hang", "mua sắm"])
    suffix = str(random.randint(10000, 9999999999))
    return f"{prefix} {suffix}"
def generate_qr_link(data: str):
    encoded = data.replace(" ", "%20")
    return f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded}"
def generate_qr_image(data: str):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    bio = io.BytesIO()
    bio.name = "qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

# ================== NẠP QUA NGÂN HÀNG ==================
async def napbank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id  # ✅ Khai báo user_id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Vui lòng nhập số tiền.\nVí dụ: /napbank 100000")
        return

    try:
        amount = int(args[0])
    except:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    if amount < 20000:
        await update.message.reply_text("❌ Nạp tối thiểu 20,000đ.")
        return

    note = generate_transfer_note()
    qr_data = f"Vietcombank | STK: 0451000123456 | Chủ TK: NGUYEN VAN A | Nội dung: {note} | Số tiền: {amount}đ"
    qr_image = generate_qr_image(qr_data)

    # Lưu giao dịch
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO deposits (user_id, amount, method, note) VALUES (%s, %s, %s, %s)",
        (user_id, amount, "bank", note)
    )
    db.commit()
    db.close()

    await update.message.reply_photo(
        photo=qr_image,
        caption=(
            f"🏦 Nạp qua ngân hàng\n\n"
            f"💰 Số tiền: {amount:,}đ\n"
            f"🔢 STK: `0451000123456`\n"
            f"👤 Chủ TK: NGUYEN VAN A\n"
            f"📝 Nội dung chuyển khoản: `{note}`\n"
            f"⏳ Hiệu lực: 5 phút\n\n"
            "⚠️ Vui lòng chuyển đúng nội dung để hệ thống tự động cộng tiền."
        ),
        parse_mode="Markdown"
    )


# ================== NẠP QUA MOMO ==================
async def momo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id  # ✅ Khai báo user_id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Vui lòng nhập số tiền.\nVí dụ: /momo 100000")
        return

    try:
        amount = int(args[0])
    except:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    if amount < 20000:
        await update.message.reply_text("❌ Nạp tối thiểu 20,000đ.")
        return

    note = generate_transfer_note()
    qr_data = f"MoMo | SĐT: 0909123456 | Chủ TK: NGUYEN VAN B | Nội dung: {note} | Số tiền: {amount}đ"
    qr_image = generate_qr_image(qr_data)

    # Lưu giao dịch
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO deposits (user_id, amount, method, note) VALUES (%s, %s, %s, %s)",
        (user_id, amount, "momo", note)
    )
    db.commit()
    db.close()

    await update.message.reply_photo(
        photo=qr_image,
        caption=(
            f"📱 Nạp qua ví MoMo\n\n"
            f"💰 Số tiền: {amount:,}đ\n"
            f"📞 Số điện thoại: `0909123456`\n"
            f"👤 Chủ TK: NGUYEN VAN B\n"
            f"📝 Nội dung chuyển tiền: `{note}`\n"
            f"⏳ Hiệu lực: 5 phút\n\n"
            "⚠️ Vui lòng chuyển đúng nội dung để hệ thống tự động cộng tiền."
        ),
        parse_mode="Markdown"
    )

# ================== TRA CỨU GIAO DỊCH ==================
async def tramanap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Vui lòng nhập nội dung chuyển khoản.")
        return

    note = " ".join(args)

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, amount, method, created_at FROM deposits WHERE note = %s", (note,))
    result = cursor.fetchone()
    db.close()

    if not result:
        await update.message.reply_text("❌ Không tìm thấy giao dịch với nội dung này.")
        return

    user_id, amount, method, created_at = result

    await update.message.reply_text(
        f"📋 Thông tin giao dịch:\n\n"
        f"👤 ID người dùng: {user_id}\n"
        f"💰 Số tiền: {amount:,}đ\n"
        f"🔄 Phương thức: {method.upper()}\n"
        f"🕒 Thời gian tạo: {created_at.strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"📝 Nội dung: {note}"
    )

# ================== XÁC NHẬN GIAO DỊCH ==================
async def donenap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Vui lòng nhập nội dung chuyển khoản.")
        return

    note = " ".join(args)

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, amount, method, status FROM deposits WHERE note = %s", (note,))
    result = cursor.fetchone()

    if not result:
        await update.message.reply_text("❌ Không tìm thấy giao dịch.")
        db.close()
        return

    user_id, amount, method, status = result

    if status == "done":
        await update.message.reply_text("⚠️ Giao dịch này đã được xử lý trước đó.")
        db.close()
        return

    # Cộng tiền
    cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    cursor.execute("UPDATE deposits SET status = 'done' WHERE note = %s", (note,))
    db.commit()
    db.close()

    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ Bạn đã nạp {method.upper()} thành công {amount:,}đ."
    )

    await update.message.reply_text(f"✅ Đã xác nhận và cộng tiền cho người dùng {user_id}.")
async def tragiaodich(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Vui lòng nhập đúng mã giao dịch.\nVí dụ: /tragiaodich 123456")
        return

    ma_giao_dich = args[0]

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT user_id, amount, bank_code, stk, name, created_at, status FROM withdraws WHERE ma_giao_dich = %s",
        (ma_giao_dich,)
    )
    result = cursor.fetchone()

    if not result:
        db.close()
        await update.message.reply_text("❌ Không tìm thấy giao dịch với mã này.")
        return

    user_id, amount, bank_code, stk, name, created_at, status = result

    # Đếm số thứ tự đơn rút
    cursor.execute(
        "SELECT ma_giao_dich FROM withdraws WHERE user_id = %s ORDER BY created_at ASC",
        (user_id,)
    )
    all_ma = [row[0] for row in cursor.fetchall()]
    db.close()

    try:
        stt = all_ma.index(ma_giao_dich) + 1
    except ValueError:
        stt = "?"

    # Trạng thái
    if status == "done":
        trang_thai = "✅ Đã chuyển khoản"
    elif status == "hoan":
        trang_thai = "❌ Hoàn tiền"
    else:
        trang_thai = f"⏳ Đang chờ xử lý (đơn rút thứ #{stt})"

    text = (
        f"📥 Yêu cầu rút tiền từ người dùng:\n\n"
        f"👤 ID: {user_id}\n"
        f"💰 Số tiền: {amount:,}đ\n"
        f"🏦 Ngân hàng: {bank_code}\n"
        f"🔢 STK: {stk}\n"
        f"👤 Chủ TK: {name}\n"
        f"🔖 Mã giao dịch: `{ma_giao_dich}`\n"
        f"🕒 Thời gian tạo: `{created_at.strftime('%d/%m/%Y %H:%M:%S')}`\n"
        f"{trang_thai}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")
#============DONE NẠP=================
async def donenap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❌ Vui lòng nhập nội dung chuyển khoản.\nVí dụ: /donenap mua hang 123456")
        return

    note = " ".join(args)

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, user_id, amount, method, status, created_at FROM deposits WHERE note = %s", (note,))
    result = cursor.fetchone()

    if not result:
        await update.message.reply_text("❌ Không tìm thấy giao dịch.")
        db.close()
        return

    deposit_id, user_id, amount, method, status, created_at = result

    if status == "done":
        await update.message.reply_text("⚠️ Giao dịch này đã được xử lý trước đó.")
        db.close()
        return

    # Cộng tiền
    cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    cursor.execute("UPDATE deposits SET status = 'done' WHERE note = %s", (note,))
    db.commit()
    db.close()

    # Thông báo cho người dùng
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ Bạn đã nạp thành công {amount:,}đ qua phương thức *{method.upper()}*.\n"
            f"📝 Nội dung: `{note}`"
        ),
        parse_mode="Markdown"
    )

    # Thông báo cho admin
    await update.message.reply_text(
        f"✅ Đã nạp cho người dùng:\n\n"
        f"👤 ID: `{user_id}`\n"
        f"💰 Số tiền: `{amount:,}đ`\n"
        f"📝 Nội dung: `{note}`\n"
        f"🕒 Thời gian: `{created_at.strftime('%d/%m/%Y %H:%M:%S')}`",
        parse_mode="Markdown"
    )

# ================== NHIỆM VỤ ==================

def mission_menu():
    kb = [
        [
            InlineKeyboardButton("🧩 Nhiệm vụ 1", callback_data="mission_1"),
            InlineKeyboardButton("🧩 Nhiệm vụ 2", callback_data="mission_2"),
            InlineKeyboardButton("🧩 Nhiệm vụ 3", callback_data="mission_3")
        ],
        [
            InlineKeyboardButton("🧩 Nhiệm vụ 4", callback_data="mission_4"),
            InlineKeyboardButton("🧩 Nhiệm vụ 5", callback_data="mission_5"),
            InlineKeyboardButton("🧩 Nhiệm vụ 6", callback_data="mission_6")
        ],
        [
            InlineKeyboardButton("🧩 Nhiệm vụ 7", callback_data="mission_7"),
            InlineKeyboardButton("🧩 Nhiệm vụ 8", callback_data="mission_8")
        ],
        [
            InlineKeyboardButton("🏆 Nhiệm vụ lớn 1", callback_data="mission_big_1"),
            InlineKeyboardButton("🏆 Nhiệm vụ lớn 2", callback_data="mission_big_2"),
            InlineKeyboardButton("🏆 Nhiệm vụ lớn 3", callback_data="mission_big_3")
        ]
    ]
    return InlineKeyboardMarkup(kb)

async def mission_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Chọn nhiệm vụ bạn muốn thực hiện:",
        reply_markup=mission_menu()
    )

def is_logged_in_recently(user_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT last_login FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()
    if not row or not row[0]:
        return False
    return (datetime.now() - row[0]).total_seconds() <= 600

# ================== NHIỆM VỤ 1 ==================
async def mission_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_1_done, mission_1_reward FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if row and row[0]:
        reward = row[1]
        phrases = [
            f"✅ Bạn đã hoàn thành Nhiệm vụ 1 trước đó. Không thể làm lại.",
            f"🎉 Nhiệm vụ 1 đã được hoàn tất!",
            f"📌 Bạn đã nhận thưởng Nhiệm vụ 1. Không thể thực hiện lại.",
            f"✅ Nhiệm vụ này đã xong rồi. Phần thưởng đã nhận được.",
            f"🎁 Bạn đã hoàn thành nhiệm vụ này trước đó."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        return

    text = (
        "🧩 *Nhiệm vụ 1*\n\n"
        "👉 Tham gia đủ 3 nhóm sau để nhận thưởng:\n"
        "1️⃣ https://t.me/nhomnv1\n"
        "2️⃣ https://t.me/nhomnvt1\n"
        "3️⃣ https://t.me/nhomnvthu1\n\n"
        "🎁 Thưởng: *1.111đ – 3.333đ*\n"
        "❗ Bạn chưa hoàn thành nhiệm vụ.\n\n"
        "➡️ Nhấn *Xác nhận* sau khi đã tham gia đủ 3 nhóm."
    )
    kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_1_check")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def mission_1_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    joined_all = True  # ← đổi thành False để test chưa hoàn thành

    if not joined_all:
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = (
            "❌ Bạn chưa tham gia đủ 3 nhóm.\n\n"
            "👉 Vui lòng tham gia:\n"
            "1️⃣ https://t.me/nhomnv1\n"
            "2️⃣ https://t.me/nhomnvt1\n"
            "3️⃣ https://t.me/nhomnvthu1\n\n"
            "➡️ Sau đó nhấn *Xác nhận* lại."
            f"\n\n📌 Kiểm tra lúc: {timestamp}"
        )
        kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_1_check")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    reward = random.randint(1111, 3333)
    db = get_db()
    c = db.cursor()
    c.execute("""
        UPDATE users SET balance=balance+%s, mission_1_done=1, mission_1_reward=%s WHERE id=%s
    """, (reward, reward, user_id))
    db.commit()
    db.close()

    await query.edit_message_text(
        f"🎉 Bạn đã hoàn thành *Nhiệm vụ 1* thành công!\n"
        f"💰 Nhận được: *{reward:,}đ*",
        parse_mode="Markdown"
    )


# ================== NHIỆM VỤ 2 ==================
async def mission_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_2_done, mission_2_reward FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()

    if row and row[0]:
        reward = row[1] if row[1] else 0
        phrases = [
            "✅ Bạn đã hoàn thành Nhiệm vụ 2 trước đó. Không thể làm lại.",
            "🎉 Nhiệm vụ 2 đã được hoàn tất!",
            "📌 Bạn đã nhận thưởng Nhiệm vụ 2. Không thể thực hiện lại.",
            "✅ Nhiệm vụ này đã xong rồi. Phần thưởng đã nhận được.",
            "🎁 Bạn đã hoàn thành nhiệm vụ này trước đó."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        db.close()
        return

    text = (
        "🧩 *Nhiệm vụ 2*\n\n"
        "👉 Nạp lần đầu *tối thiểu 20.000đ* để nhận thưởng:\n"
        "💳 Sau khi nạp, nhấn nút *Xác nhận* bên dưới để nhận quà.\n\n"
        "🎁 Thưởng: *5.000đ – 10.000đ*\n"
        "❗ Chỉ áp dụng cho lần nạp đầu tiên.\n\n"
        "➡️ Nhấn *Xác nhận* sau khi đã nạp."
    )
    kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_2_check")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def mission_2_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT MIN(id), amount FROM deposits WHERE user_id=%s ORDER BY id ASC LIMIT 1", (user_id,))
    first_deposit = c.fetchone()
    amount = first_deposit[1] if first_deposit else 0

    if amount < 20000:
        await query.edit_message_text(
            "❌ Bạn chưa thực hiện giao dịch nạp nào đủ điều kiện.\n\n"
            "👉 Vui lòng nạp *tối thiểu 20.000đ* rồi quay lại xác nhận.",
            parse_mode="Markdown"
        )
        db.close()
        return

    reward = random.randint(5000, 10000)
    c.execute("""
        UPDATE users
        SET balance = balance + %s,
            mission_2_done = 1,
            mission_2_reward = %s
        WHERE id = %s
    """, (reward, reward, user_id))
    db.commit()
    db.close()

    await query.edit_message_text(
        f"🎉 Bạn đã hoàn thành *Nhiệm vụ 2* thành công!\n"
        f"💰 Nhận được: *{reward:,}đ*",
        parse_mode="Markdown"
    )


# ================== NHIỆM VỤ 3 ==================
async def mission_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    # Kiểm tra đã hoàn thành chưa
    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_3_done FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if row and row[0]:
        c = get_db().cursor()
        c.execute("SELECT mission_3_reward FROM users WHERE id=%s", (user_id,))
        reward_row = c.fetchone()
        reward = reward_row[0] if reward_row else 0
        phrases = [
            f"✅ Bạn đã hoàn thành Nhiệm vụ 3 trước đó. Không thể làm lại.",
            f"🎉 Nhiệm vụ 3 đã được hoàn tất!",
            f"📌 Bạn đã nhận thưởng Nhiệm vụ 3. Không thể thực hiện lại.",
            f"✅ Nhiệm vụ này đã xong rồi. Phần thưởng đã nhận được.",
            f"🎁 Bạn đã hoàn thành nhiệm vụ này trước đó."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        return

    # Hiển thị nội dung nhiệm vụ
    text = (
        "🧩 *Nhiệm vụ 3: Mời bạn bè*\n\n"
        "👉 Mời đủ *10 người dùng* đăng ký qua liên kết giới thiệu của bạn để nhận thưởng.\n"
        "🔗 Sau khi đủ, nhấn nút *Xác nhận* bên dưới để nhận quà.\n\n"
        "🎁 Thưởng: *5.555đ – 8.888đ*\n"
        "❗ Chỉ áp dụng cho người mời đủ 10 người thật sự.\n\n"
        "➡️ Nhấn *Xác nhận* sau khi đã mời đủ."
    )
    kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_3_check")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
async def mission_3_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    # Kiểm tra đăng nhập
    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()

    # Kiểm tra đã hoàn thành chưa
    c.execute("SELECT mission_3_done, mission_3_reward FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    if row and row[0]:  # mission_3_done = 1
        reward = row[1] or 0
        phrases = [
            f"✅ Bạn đã hoàn thành Nhiệm vụ 3 trước đó. Không thể làm lại.",
            f"🎉 Nhiệm vụ 3 đã được hoàn tất!",
            f"📌 Bạn đã nhận thưởng Nhiệm vụ 3. Không thể thực hiện lại.",
            f"✅ Nhiệm vụ này đã xong rồi. Phần thưởng đã nhận được.",
            f"🎁 Bạn đã hoàn thành nhiệm vụ này trước đó."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        db.close()
        return

    # Lấy tổng số người đã mời từ cột invited_total
    c.execute("SELECT invited_total FROM users WHERE id=%s", (user_id,))
    invited_row = c.fetchone()
    invited_count = invited_row[0] if invited_row else 0

    if invited_count < 10:
        await query.edit_message_text(
            f"❌ Bạn mới mời được *{invited_count} người*. Chưa đủ điều kiện nhận thưởng.\n\n"
            "👉 Vui lòng mời đủ *10 người dùng* rồi quay lại xác nhận.",
            parse_mode="Markdown"
        )
        db.close()
        return

    # Cộng thưởng
    reward = random.randint(5555, 8888)
    c.execute("""
        UPDATE users SET balance = balance + %s, mission_3_done = 1, mission_3_reward = %s WHERE id = %s
    """, (reward, reward, user_id))
    db.commit()
    db.close()

    await query.edit_message_text(
        f"🎉 Bạn đã hoàn thành *Nhiệm vụ 3* thành công!\n"
        f"💰 Nhận được: *{reward:,}đ*",
        parse_mode="Markdown"
    )

#=============== NHIỆM VỤ 4 =================
async def mission_4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = None
    try:
        db = get_db()
        if not db.is_connected():
            db.reconnect()
        c = db.cursor()

        c.execute("SELECT mission_4_last_claim FROM users WHERE id=%s", (user_id,))
        row = c.fetchone()
        last_claim = row[0] if row else None

        if last_claim == date.today():
            phrases = [
                "✅ Bạn đã nhận thưởng Nhiệm vụ 4 hôm nay rồi.",
                "🎉 Nhiệm vụ 4 hôm nay đã hoàn tất!",
                "📌 Bạn đã nhận quà nhiệm vụ này hôm nay.",
                "✅ Nhiệm vụ này chỉ nhận 1 lần mỗi ngày.",
                "🎁 Bạn đã hoàn thành nhiệm vụ 4 hôm nay."
            ]
            await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
            return

        text = (
            "🎯 *Nhiệm vụ 4 (hàng ngày)*\n\n"
            "👉 Quay slot phòng *Thường* đủ *50 lần hôm nay* để nhận thưởng:\n"
            "🎰 Sau khi đủ lượt, nhấn nút *Xác nhận* bên dưới để nhận quà.\n\n"
            "🎁 Thưởng: *2.000đ*\n"
            "❗ Có thể làm lại mỗi ngày.\n\n"
            "➡️ Nhấn *Xác nhận* sau khi đã quay đủ."
        )
        text += f"\n\n🕒 Cập nhật lúc: {datetime.now().strftime('%H:%M:%S')}"
        kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_4_check")]]

        try:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise

    except mysql.connector.Error as err:
        await query.edit_message_text(f"❌ Lỗi MySQL:\n`{err}`", parse_mode="Markdown")
    finally:
        if db:
            try:
                db.close()
            except:
                pass


async def mission_4_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = None
    try:
        db = get_db()
        if not db.is_connected():
            db.reconnect()
        c = db.cursor()

        c.execute("SELECT mission_4_last_claim, slot_count_normal FROM users WHERE id=%s", (user_id,))
        row = c.fetchone()
        last_claim = row[0] if row else None
        slot_count = row[1] if row else 0

        if last_claim == date.today():
            await query.edit_message_text(
                "✅ Bạn đã nhận thưởng Nhiệm vụ 4 hôm nay rồi.",
                parse_mode="Markdown"
            )
            return

        if slot_count < 50:
            await query.edit_message_text(
                f"❌ Bạn mới quay *{slot_count} lần* phòng Thường hôm nay.\n\n"
                f"👉 Cần quay đủ *50 lần* để nhận thưởng.",
                parse_mode="Markdown"
            )
            return

        reward = 2000
        c.execute("""
            UPDATE users
            SET balance = balance + %s,
                mission_4_reward = %s,
                mission_4_last_claim = %s
            WHERE id = %s
        """, (reward, reward, date.today(), user_id))
        db.commit()

        await query.edit_message_text(
            f"🎉 Bạn đã hoàn thành *Nhiệm vụ 4 hôm nay*!\n"
            f"💰 Nhận được: *{reward:,}đ*",
            parse_mode="Markdown"
        )

    except mysql.connector.Error as err:
        await query.edit_message_text(f"❌ Lỗi MySQL:\n`{err}`", parse_mode="Markdown")
    finally:
        if db:
            try:
                db.close()
            except:
                pass


#=============== NHIỆM VỤ 5 =================
async def mission_5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_5_last_claim FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    today = date.today()
    last_claim = row[0] if row else None

    if last_claim == today:
        phrases = [
            "✅ Bạn đã nhận thưởng nhiệm vụ 5 hôm nay rồi.",
            "🎉 Nhiệm vụ 5 hôm nay đã hoàn tất!",
            "📌 Mỗi ngày chỉ nhận 1 lần.",
            "✅ Quay lại vào ngày mai để nhận tiếp nhé!",
            "🎁 Bạn đã nhận quà nhiệm vụ 5 hôm nay."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        db.close()
        return

    text = (
        "🎯 *Nhiệm vụ 5*\n\n"
        "🏆 Thắng *Nổ Hũ* tại phòng *Thường* để nhận thưởng:\n"
        "💥 Khi bạn quay ra 3 icon *🏆* hàng ngang hoặc chéo, bạn sẽ nổ hũ.\n\n"
        "🎁 Thưởng: *30.000đ*\n"
        "❗ Mỗi ngày chỉ nhận 1 lần.\n\n"
        "➡️ Nhấn *Xác nhận* sau khi đã nổ hũ."
    )
    kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_5_check")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    db.close()


async def mission_5_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    today = date.today()
    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_5_last_claim, mission_5_triggered FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    last_claim, triggered = row if row else (None, 0)

    if last_claim == today:
        phrases = [
            "✅ Bạn đã nhận thưởng nhiệm vụ 5 hôm nay rồi.",
            "🎉 Nhiệm vụ 5 hôm nay đã hoàn tất!",
            "📌 Mỗi ngày chỉ nhận 1 lần.",
            "✅ Quay lại vào ngày mai để nhận tiếp nhé!",
            "🎁 Bạn đã nhận quà nhiệm vụ 5 hôm nay."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        db.close()
        return

    if not triggered:
        await query.edit_message_text(
            "❌ Bạn chưa thắng *Nổ Hũ* tại phòng Thường.\n\n"
            "👉 Vui lòng quay slot phòng Thường và nổ hũ trước khi xác nhận.",
            parse_mode="Markdown"
        )
        db.close()
        return

    reward = 30000
    c.execute("""
        UPDATE users
        SET balance = balance + %s,
            mission_5_last_claim = %s,
            mission_5_triggered = 0
        WHERE id = %s
    """, (reward, today, user_id))
    db.commit()
    db.close()

    await query.edit_message_text(
        f"🎉 Bạn đã hoàn thành *Nhiệm vụ 5* hôm nay!\n"
        f"💰 Nhận được: *{reward:,}đ*",
        parse_mode="Markdown"
    )
#============NHIỆM VỤ 6============
async def mission_6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_6_done FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if row and row[0]:
        phrases = [
            "✅ Bạn đã nhận thưởng nhiệm vụ 6 rồi.",
            "🎉 Nhiệm vụ 6 đã hoàn tất!",
            "📌 Mỗi tài khoản chỉ nhận 1 lần.",
            "🎁 Bạn đã nhận quà nhiệm vụ 6 trước đó.",
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        return

    text = (
        "🎯 *Nhiệm vụ 6*\n\n"
        "✅ Hoàn thành ít nhất *3 nhiệm vụ bất kỳ* trong các nhiệm vụ 1–5.\n"
        "🎁 Thưởng: *5.000đ*\n"
        "❗ Chỉ nhận *1 lần duy nhất*.\n\n"
        "➡️ Nhấn *Xác nhận* sau khi đã hoàn thành đủ điều kiện."
    )
    kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_6_check")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def mission_6_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT mission_1_done, mission_2_done, mission_3_done, mission_4_done, mission_5_done, mission_6_done
        FROM users WHERE id=%s
    """, (user_id,))
    row = c.fetchone()
    if not row:
        await query.edit_message_text("❌ Không tìm thấy tài khoản.", parse_mode="Markdown")
        db.close()
        return

    m1, m2, m3, m4, m5, m6 = row
    completed = sum([bool(m1), bool(m2), bool(m3), bool(m4), bool(m5)])

    if m6:
        phrases = [
            "✅ Bạn đã nhận thưởng nhiệm vụ 6 rồi.",
            "🎉 Nhiệm vụ 6 đã hoàn tất!",
            "📌 Mỗi tài khoản chỉ nhận 1 lần.",
            "🎁 Bạn đã nhận quà nhiệm vụ 6 trước đó.",
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        db.close()
        return

    if completed < 3:
        await query.edit_message_text(
            "❌ Bạn chưa hoàn thành đủ *3 nhiệm vụ bất kỳ*.\n\n"
            "👉 Vui lòng hoàn thành thêm nhiệm vụ trước khi xác nhận.",
            parse_mode="Markdown"
        )
        db.close()
        return

    reward = 5000
    c.execute("""
        UPDATE users
        SET balance = balance + %s,
            mission_6_done = TRUE
        WHERE id = %s
    """, (reward, user_id))
    db.commit()
    db.close()

    await query.edit_message_text(
        f"🎉 Bạn đã hoàn thành *Nhiệm vụ 6*!\n"
        f"💰 Nhận được: *{reward:,}đ*",
        parse_mode="Markdown"
    )


#======== NHIỆM VỤ LỚN 1 ============
async def mission_big_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để thực hiện nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()
    c.execute("SELECT mission_big_1_done FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if row and row[0]:
        c = get_db().cursor()
        c.execute("SELECT mission_big_1_reward FROM users WHERE id=%s", (user_id,))
        reward_row = c.fetchone()
        reward = reward_row[0] if reward_row else 0
        phrases = [
            f"✅ Bạn đã hoàn thành Nhiệm vụ lớn 1 trước đó. Không thể làm lại.",
            f"🎉 Nhiệm vụ lớn 1 đã được hoàn tất!",
            f"📌 Bạn đã nhận thưởng Nhiệm vụ lớn 1. Không thể thực hiện lại.",
            f"✅ Nhiệm vụ này đã xong rồi. Phần thưởng đã nhận được.",
            f"🎁 Bạn đã hoàn thành nhiệm vụ này trước đó."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        return

    text = (
        "🏆 *Nhiệm vụ lớn 1*\n\n"
        "👉 Nạp *một lần duy nhất từ 100.000đ trở lên* để nhận thưởng:\n"
        "💳 Sau khi nạp, nhấn nút *Xác nhận* bên dưới để nhận quà.\n\n"
        "🎁 Thưởng: *10.000đ – 30.000đ*\n"
        "❗ Chỉ áp dụng cho lần nạp đầu tiên ≥ 100.000đ.\n\n"
        "➡️ Nhấn *Xác nhận* sau khi đã nạp."
    )
    kb = [[InlineKeyboardButton("✅ Xác nhận", callback_data="mission_big_1_check")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def mission_big_1_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang kiểm tra...")
    user_id = query.from_user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    if not is_logged_in_recently(user_id):
        await query.edit_message_text(
            "🔐 Bạn cần đăng nhập để xác nhận nhiệm vụ này.\n\n"
            "Vui lòng dùng lệnh:\n`/login <mật khẩu>`",
            parse_mode="Markdown"
        )
        return

    db = get_db()
    c = db.cursor()

    c.execute("SELECT mission_big_1_done FROM users WHERE id=%s", (user_id,))
    if c.fetchone()[0]:
        c.execute("SELECT mission_big_1_reward FROM users WHERE id=%s", (user_id,))
        reward_row = c.fetchone()
        reward = reward_row[0] if reward_row else 0
        phrases = [
            f"✅ Bạn đã hoàn thành Nhiệm vụ lớn 1 trước đó. Không thể làm lại.",
            f"🎉 Nhiệm vụ lớn 1 đã được hoàn tất!",
            f"📌 Bạn đã nhận thưởng Nhiệm vụ lớn 1. Không thể thực hiện lại.",
            f"✅ Nhiệm vụ này đã xong rồi. Phần thưởng đã nhận được.",
            f"🎁 Bạn đã hoàn thành nhiệm vụ này trước đó."
        ]
        await query.edit_message_text(random.choice(phrases), parse_mode="Markdown")
        db.close()
        return

    c.execute("SELECT MAX(amount) FROM deposits WHERE user_id=%s", (user_id,))
    max_deposit = c.fetchone()[0] or 0

    if max_deposit < 100000:
        await query.edit_message_text(
            "❌ Bạn chưa thực hiện giao dịch nạp nào đủ điều kiện.\n\n"
            "👉 Vui lòng nạp *tối thiểu 100.000đ trong một lần* rồi quay lại xác nhận.",
            parse_mode="Markdown"
        )
        db.close()
        return

    reward = random.randint(10000, 30000)
    c.execute("""
        UPDATE users SET balance=balance+%s, mission_big_1_done=1, mission_big_1_reward=%s WHERE id=%s
    """, (reward, reward, user_id))
    db.commit()
    db.close()

    await query.edit_message_text(
        f"🎉 Bạn đã hoàn thành *Nhiệm vụ lớn 1* thành công!\n"
        f"💰 Nhận được: *{reward:,}đ*",
        parse_mode="Markdown"
    )
#================QUAY SLOT===================
async def slot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    message = update.effective_message
    send_func = query.edit_message_text if query else message.reply_text

    # ✅ Lấy user_id và chặn người bị ban
    user_id = update.effective_user.id
    if is_banned(user_id):
        return  # Không phản hồi nếu bị ban

    db = get_db()
    c = db.cursor()
    try:
        c.execute("SELECT jackpot_normal, jackpot_vip, jackpot_super FROM `system` LIMIT 1")
        row = c.fetchone()
        if c.with_rows:
            c.fetchall()
        jackpot_normal, jackpot_vip, jackpot_super = row if row else (30000, 80000, 150000)
    except Exception as e:
        await send_func(f"❌ Lỗi truy vấn hũ: `{e}`", parse_mode="Markdown")
        db.close()
        return
    db.close()

    text = (
        "🎰 *Slot Machine – Quay để nhận thưởng!*\n\n"
        "📜 *Cách thắng:*\n"
        "– 3 icon khác nhau → ❌ Thua\n"
        "– 3 icon giống nhau:\n"
        "   😁 → x2 | 😆 → x2.5 | 🤩 → x5\n"
        "   🥳 → x10 | 🤑 → x20 | 🤯 → x30\n"
        "   😱 → x50 | 🏆 → Nổ Hũ\n\n"
        f"💰 *Hũ hiện tại:*\n"
        f"– Thường: *{jackpot_normal:,}đ*\n"
        f"– VIP: *{jackpot_vip:,}đ*\n"
        f"– Siêu cấp: *{jackpot_super:,}đ*\n\n"
        "🎯 *Chọn phòng để quay:*"
    )

    kb = [
        [InlineKeyboardButton("🎮 Thường", callback_data="slot_play_normal")],
        [InlineKeyboardButton("💎 VIP", callback_data="slot_play_vip")],
        [InlineKeyboardButton("🚀 Siêu Cấp", callback_data="slot_play_super")]
    ]
    await send_func(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def slot_play(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str, message=None, user=None):
    query = update.callback_query if update.callback_query else None
    message = message or update.effective_message
    user = user or update.effective_user
    user_id = user.id

    # ✅ Chặn người bị ban
    if is_banned(user_id):
        return

    context.user_data.setdefault(user_id, {})

    send_func = (
        query.edit_message_text
        if query and query.from_user.id == user_id
        else message.reply_text
    )

    config = {
        "normal": {"bet": 500, "base": 30000, "rate": 0.003, "col": "jackpot_normal", "count": "slot_count_normal"},
        "vip": {"bet": 2000, "base": 80000, "rate": 0.005, "col": "jackpot_vip", "count": "slot_count_vip"},
        "super": {"bet": 5000, "base": 150000, "rate": 0.003, "col": "jackpot_super", "count": "slot_count_super"}
    }
    if mode not in config:
        return await send_func(text="❌ Phòng không hợp lệ.")

    bet, base, rate, col, count = config[mode].values()
    db = get_db()
    c = db.cursor()

    try:
        c.execute("SELECT amount FROM deposits WHERE user_id=%s AND amount>=50000 LIMIT 1", (user_id,))
        if not c.fetchone():
            return await send_func(text="❌ Bạn cần có ít nhất 1 đơn nạp từ *50,000đ* mới được chơi.", parse_mode="Markdown")

        c.execute(f"SELECT balance, {count} FROM users WHERE id=%s", (user_id,))
        row = c.fetchone()
        if c.with_rows:
            c.fetchall()
        if not row or row[0] is None:
            return await send_func(text="❌ Không thể lấy thông tin tài khoản.", parse_mode="Markdown")

        bal, spins = row
        if bal < bet:
            return await send_func(text=f"❌ Không đủ tiền. Cần *{bet:,}đ*", parse_mode="Markdown")

        c.execute(f"UPDATE users SET balance=balance-%s, {count}={count}+1 WHERE id=%s", (bet, user_id))

        icons = ["😁", "😆", "😱", "🤩", "🥳", "🤑", "🤯", "🏆"]
        grid = [[random.choice(icons) for _ in range(3)] for _ in range(3)]

        c.execute(f"SELECT {col} FROM `system` LIMIT 1")
        jackpot_row = c.fetchone()
        if c.with_rows:
            c.fetchall()
        jackpot = jackpot_row[0] if jackpot_row else base
        reward = 0

        for row in grid:
            if len(set(row)) == 1:
                icon = row[0]
                break
        else:
            if grid[0][0] == grid[1][1] == grid[2][2]:
                icon = grid[0][0]
            elif grid[0][2] == grid[1][1] == grid[2][0]:
                icon = grid[0][2]
            else:
                icon = None

        if icon:
            multi = {
                "😁": 2, "😆": 2.5, "😱": 50, "🤩": 5,
                "🥳": 10, "🤑": 20, "🤯": 30, "🏆": "jackpot"
            }.get(icon, 0)
            reward = jackpot if multi == "jackpot" else int(bet * multi)
            if multi == "jackpot":
                c.execute(f"UPDATE `system` SET {col}=%s", (base,))
                c.execute("INSERT INTO jackpot_history (user_id, room, amount) VALUES (%s, %s, %s)", (user_id, mode, reward))

        jackpot_add = int(bet * rate)
        c.execute(f"UPDATE `system` SET {col}={col}+%s", (jackpot_add,))
        if reward:
            c.execute("UPDATE users SET balance=balance+%s WHERE id=%s", (reward, user_id))

        db.commit()
    except Exception as e:
        return await send_func(text=f"❌ Lỗi xử lý: `{e}`", parse_mode="Markdown")
    finally:
        db.close()

    grid_txt = "\n".join([f"| {' | '.join(row)} |" for row in grid])
    text = (
        f"🎰 *Phòng {mode.upper()}*\n"
        f"💰 Hũ: *{jackpot:,}đ* | 👤 Số dư: *{bal - bet + reward:,}đ*\n"
        f"🔄 Lượt quay hôm nay: *{spins + 1}*\n"
        f"─────────────────\n<<<OkNha>>>\n{grid_txt}\n///////////////////\n"
        f"💸 *Min:* {bet:,}đ | 🏆 *Thắng:* {reward:,}đ"
    )

    kb = [
        [
            InlineKeyboardButton("🔁 Spin tiếp", callback_data=f"slot_play_{mode}"),
            InlineKeyboardButton("📜 Lịch sử nổ hũ", callback_data="slot_history")
        ],
        [
            InlineKeyboardButton("↩️ Menu", callback_data="slot_menu")
        ]
    ]
    await send_func(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def slot_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db = get_db()
    c = db.cursor()
    c.execute("SELECT user_id, room, amount, timestamp FROM jackpot_history ORDER BY timestamp DESC LIMIT 10")
    rows = c.fetchall()
    db.close()

    if not rows:
        return await query.edit_message_text(text="📜 Chưa có ai nổ hũ!")

    text = "*📜 Top 10 người nổ hũ gần nhất:*\n\n"
    for i, (uid, room, amount, ts) in enumerate(rows, 1):
        time_str = ts.strftime("%d/%m/%Y %H:%M")
        text += f"{i}. 👤 ID: `{uid}` | 💥 Phòng: *{room.upper()}* | 💰 {amount:,}đ\n🕒 {time_str}\n\n"

    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Quay lại", callback_data="slot_menu")]
        ])
    )

#==============GỬI THÔNG BÁO========
async def guithongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Dùng đúng cú pháp:\n/guithongbao <người gửi>\nNội dung ở dòng kế tiếp hoặc cùng dòng.")

    sender = context.args[0]
    # Lấy nội dung sau dòng đầu tiên
    content_lines = update.message.text.split("\n")[1:]
    content = "\n".join(content_lines).strip()

    # Nếu không có dòng xuống, lấy nội dung từ cùng dòng
    if not content:
        content = update.message.text.partition(" ")[2].replace(sender, "", 1).strip()

    if not content:
        return await update.message.reply_text("❌ Bạn chưa nhập nội dung thông báo.")

    db = get_db()
    c = db.cursor()
    c.execute("REPLACE INTO notifications (sender, content, timestamp) VALUES (%s, %s, NOW())", (sender, content))
    db.commit()

    c.execute("SELECT id FROM users")
    user_ids = [row[0] for row in c.fetchall()]
    db.close()

    success = 0
    fail = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 *Thông báo từ {sender}:*\n\n{content}", parse_mode="Markdown")
            success += 1
        except:
            fail += 1

    await update.message.reply_text(
        f"✅ Đã gửi thông báo từ *{sender}*\n"
        f"📬 Thành công: *{success}* người\n"
        f"⚠️ Thất bại: *{fail}*", parse_mode="Markdown"
    )


#==============ĐỌC THÔNG BÁO========
async def doc_thongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Dùng đúng cú pháp: /doc <người gửi>")

    sender = context.args[0]
    db = get_db()
    c = db.cursor()
    c.execute("SELECT content, timestamp FROM notifications WHERE sender=%s", (sender,))
    row = c.fetchone()
    db.close()

    if not row:
        return await update.message.reply_text(f"❌ Không có thông báo từ *{sender}*", parse_mode="Markdown")

    content, timestamp = row
    await update.message.reply_text(
        f"📢 *Thông báo từ {sender}:*\n\n{content}\n\n🕒 Gửi lúc: {timestamp.strftime('%d/%m/%Y %H:%M:%S')}",
        parse_mode="Markdown"
    )


#==============GỠ THÔNG BÁO========
async def gothongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Dùng đúng cú pháp: /gothongbao <người gửi>")

    sender = context.args[0]
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM notifications WHERE sender=%s", (sender,))
    db.commit()
    db.close()

    await update.message.reply_text(f"✅ Đã gỡ thông báo từ *{sender}*", parse_mode="Markdown")


#==============NÚT THÔNG BÁO========
async def thongbao_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT sender FROM notifications")
    senders = [row[0] for row in c.fetchall()]
    db.close()

    if not senders:
        return await update.message.reply_text("📢 Hiện tại chưa có thông báo nào.")

    kb = [[InlineKeyboardButton(f"📨 {sender}", callback_data=f"view_post_{sender}")] for sender in senders]
    await update.message.reply_text(
        f"📢 Có *{len(senders)}* thông báo đang hoạt động:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )


#==============XEM NỘI DUNG THÔNG BÁO========
async def view_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sender = query.data.replace("view_post_", "")
    db = get_db()
    c = db.cursor()
    c.execute("SELECT content, timestamp FROM notifications WHERE sender=%s", (sender,))
    row = c.fetchone()
    db.close()

    if not row:
        return await query.edit_message_text(f"❌ Không có thông báo từ *{sender}*", parse_mode="Markdown")

    content, timestamp = row
    await query.edit_message_text(
        f"📢 *Thông báo từ {sender}:*\n\n{content}\n\n🕒 Gửi lúc: {timestamp.strftime('%d/%m/%Y %H:%M:%S')}",
        parse_mode="Markdown"
    )
#===========BAN USER===========

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_banned(user_id: int) -> bool:
    db = get_db()
    c = db.cursor()
    c.execute("SELECT banned_until FROM users WHERE id=%s", (user_id,))
    row = c.fetchone()
    db.close()

    if not row or not row[0]:
        return False

    return datetime.now() < row[0]


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")

    args = context.args
    if len(args) < 3:
        return await update.message.reply_text("❌ Cú pháp: /ban <id> <số giờ> <lý do>")

    try:
        target_id = int(args[0])
        hours = int(args[1])
        reason = " ".join(args[2:])
        unlock_time = datetime.now() + timedelta(hours=hours)

        db = get_db()
        c = db.cursor()
        c.execute("UPDATE users SET banned_until=%s, ban_reason=%s WHERE id=%s", (unlock_time, reason, target_id))
        db.commit()
        db.close()

        await update.message.reply_text(
            f"✅ Đã ban user `{target_id}` trong {hours} giờ.\n📌 Lý do: {reason}",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🚫 Bạn đã bị ban khỏi bot.\n"
                    f"⏳ Thời gian mở khóa: *{unlock_time.strftime('%d/%m/%Y %H:%M')}*\n"
                    f"📌 Lý do: {reason}"
                ),
                parse_mode="Markdown"
            )
        except:
            pass  # Người dùng chưa từng chat với bot
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi xử lý: {e}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")

    args = context.args
    if len(args) != 1:
        return await update.message.reply_text("❌ Cú pháp: /unban <id>")

    try:
        target_id = int(args[0])
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE users SET banned_until=NULL, ban_reason=NULL WHERE id=%s", (target_id,))
        db.commit()
        db.close()

        await update.message.reply_text(f"✅ Đã mở khóa user `{target_id}`", parse_mode="Markdown")

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ Bạn đã được mở khóa và có thể sử dụng bot trở lại."
            )
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi xử lý: {e}")

#======== MAIN ==================
def main():
    create_tables()
    app = ApplicationBuilder().token(BOT_TOKEN).build()


    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("creatacc", creatacc))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("mokhoa", mokhoa))
    app.add_handler(CommandHandler("naptien", admin_naptien))
    app.add_handler(CommandHandler("trutien", admin_trutien))
    app.add_handler(CommandHandler("rutbank", rutbank))
    app.add_handler(CallbackQueryHandler(rutbank_callback, pattern="^(confirm_rut|cancel_rut)"))
    app.add_handler(CallbackQueryHandler(rutbank_callback, pattern="^(confirm_rut_|cancel_rut_)"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CommandHandler("napbank", napbank))
    app.add_handler(CommandHandler("momo", momo))
    app.add_handler(CommandHandler("napthe", napthe))
    app.add_handler(CommandHandler("tramanap", tramanap))
    app.add_handler(CommandHandler("donenap", donenap))
    app.add_handler(CallbackQueryHandler(xu_ly_thecao_callback, pattern="^(chuyen_|sua_)"))
    app.add_handler(CallbackQueryHandler(xu_ly_admin_thecao, pattern="^(cong_|hoan_)"))
    app.add_handler(CommandHandler("morut", morut))
    app.add_handler(CommandHandler("tatrut", tatrut))
    app.add_handler(CommandHandler("tragiaodich", tragiaodich))
    app.add_handler(CommandHandler("doimatkhau", doimatkhau))
    app.add_handler(CommandHandler("setpass", setpass))
    app.add_handler(CallbackQueryHandler(mission_1, pattern="^mission_1$"))
    app.add_handler(CallbackQueryHandler(mission_1_check, pattern="^mission_1_check$"))
    app.add_handler(CallbackQueryHandler(mission_2, pattern="^mission_2$"))
    app.add_handler(CallbackQueryHandler(mission_2_check, pattern="^mission_2_check$"))
    app.add_handler(CallbackQueryHandler(mission_big_1, pattern="^mission_big_1$"))
    app.add_handler(CallbackQueryHandler(mission_big_1_check, pattern="^mission_big_1_check$"))
    app.add_handler(CallbackQueryHandler(mission_3, pattern=r"^mission_3$"))
    app.add_handler(CallbackQueryHandler(mission_3_check, pattern=r"^mission_3_check$"))
    app.add_handler(CallbackQueryHandler(mission_4, pattern="^mission_4$"))
    app.add_handler(CallbackQueryHandler(mission_4_check, pattern="^mission_4_check$"))
    app.add_handler(CallbackQueryHandler(mission_5, pattern="^mission_5$"))
    app.add_handler(CallbackQueryHandler(mission_5_check, pattern="^mission_5_check$"))
    app.add_handler(CommandHandler("guithongbao", guithongbao))
    app.add_handler(CommandHandler("doc", doc_thongbao))
    app.add_handler(CommandHandler("gothongbao", gothongbao))
    app.add_handler(CallbackQueryHandler(view_post, pattern="^view_post_"))
    app.add_handler(CallbackQueryHandler(slot_menu, pattern="^slot_menu$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: slot_play(u, c, "normal"), pattern="^slot_play_normal$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: slot_play(u, c, "vip"), pattern="^slot_play_vip$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: slot_play(u, c, "super"), pattern="^slot_play_super$"))
    app.add_handler(CallbackQueryHandler(mission_6, pattern="^mission_6$"))
    app.add_handler(CallbackQueryHandler(mission_6_check, pattern="^mission_6_check$"))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))

    CallbackQueryHandler(mission_1_check, pattern="^mission_1_check$")
    app.add_handler(CallbackQueryHandler(slot_history, pattern="^slot_history$"))

    app.add_handler(MessageHandler(filters.Text("ℹ️ Thông tin"), info))
    app.add_handler(MessageHandler(filters.Text("🤝 Mời bạn bè"), invite))
    app.add_handler(MessageHandler(filters.Text(["🏦 Rút tiền"]), rut_tien_menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💳 Nạp tiền$"), xu_ly_nap_tien))
    app.add_handler(MessageHandler(filters.Text("📌 Nhiệm vụ"), mission_entry))
    app.add_handler(MessageHandler(filters.Regex("^🎰 Quay Slot$"), slot_menu))
    app.add_handler(MessageHandler(filters.Regex("^📢 Thông báo$"), thongbao_message))

    app.add_handler(CallbackQueryHandler(confirm_acc, pattern="confirm_acc"))
    app.add_handler(CallbackQueryHandler(cancel_acc, pattern="cancel_acc"))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("nap_tien_huong_dan", nap_tien_huong_dan))


    app.run_polling()

if __name__ == "__main__":
    main()
