import os, logging, sys

API_ID = 35705631
API_HASH = "f99495d459f190bb24c74d309a8d635e"
BOT_TOKEN = "8995626075:AAG03qYcSoiwIxwxkdmlE6ownW-ppyrmwIk"

DB_URI = os.environ.get("DATABASE_URL", "")
DB_NAME = os.environ.get("DATABASE_NAME", "")

PORT = 6000
OWNER_ID = 8531722224
ADMINS = [OWNER_ID,8531722224]
TG_BOT_WORKERS = 4

VERIFY_EXPIRE = 12 * 3600
DB_ID = -1004362567395
CHANNEL_ID = -1004362567395
waiting_timer_status = False
REFERRAL_REWARD_DAYS = 1
BYPASS_LIMIT = 1

PICS = [
    "https://i.postimg.cc/3R0rnHFb/image.png"
]

ADMIN_CONTACT_LINK = "https://t.me/salesgodx"


commands = [
    "start","help","myplan","refer","id","set_free_limit","reset_free_count","update",
    "verification","admin","free","toggle_refer","check_refers","addadmin","deladmin",
    "listadmin","stats","ban","unban","dbroadcast","broadcast","listfsub","delfsub",
    "addfsub","del_shortner","list_shortner","add_shortner","status","addpaid",'scrapper',
    "removepaid","listpaid","restart","set","cleanup","adddump","deldump",'reqfsub','genlink',
    "listdump","layout","hmanga","waiting_timer","batch","video","envelope",'banlist','listban','ronak','restricted','r','verify'
]

ADMIN_CMD = [
    "set_free_limit","reset_free_count","update","batch","scrapper",
    "waiting_timer","verification","admin","free","toggle_refer","check_refers",
    "addadmin","deladmin","listadmin","stats","ban","unban","dbroadcast","broadcast",
    "listfsub","delfsub","addfsub","del_shortner","list_shortner","add_shortner",
    "status","addpaid","removepaid","listpaid","restart","set","cleanup",
    "adddump","deldump","listdump","layout","hmanga","envelope",'banlist','listban','ronak',
    'reqfsub'
]
# ------------------ PAYMENT ACCOUNTS ------------------

PAYMENT_ACCOUNTS = {
    "ronak": {
        "upi": "BHARATPE2P0Y0X1Y3L02804@unitype",
        "merchant": "sPATsm3k9982251499052"
    },
    "kartik": {
        "upi": "BHARATPE2P0Y0X1Y3L02804@unitype",
        "merchant": "YPfQEi05426608236469"
    }
}
# Default account
ACTIVE_PAYMENT = "kartik"
# UPI_ID = ""
# MERCHANT_ID = ""

PLANS = [
    {"days": 1,   "price": "₹15",  "label": "1 𝖣𝖠𝖸"},
    {"days": 7,   "price": "₹59",  "label": "7 𝖣𝖠𝖸𝖲"},
    {"days": 30,  "price": "₹129", "label": "1 𝖬𝖮𝖭𝖳𝖧"},
    {"days": 90,  "price": "₹279", "label": "3 𝖬𝖮𝖭𝖳𝖧𝖲"},
    {"days": 180, "price": "₹449", "label": "6 𝖬𝖮𝖭𝖳𝖧𝖲"},
    {"days": 365, "price": "₹749", "label": "1 𝖸𝖤𝖠𝖱"},
]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = lambda name: logging.getLogger(name)
