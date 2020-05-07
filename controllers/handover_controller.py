import os
import logging
import configparser
from twilio.rest import Client

logger = logging.getLogger("Human Handover Controller")
logger.setLevel(logging.INFO)
# create file handler which logs even debug messages
log_file_handler = logging.FileHandler("covid_chatbot.log")
log_file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s,%(msecs)d - %(name)s - %(levelname)s - %(message)s")
log_file_handler.setFormatter(formatter)
logger.addHandler(log_file_handler)

# load configs from config.ini file
config = configparser.ConfigParser(inline_comment_prefixes="#")
config.read(os.path.join(os.path.dirname(__file__), "..", "config.ini"))
twilio_settings = config["TWILIO"]

try:
    logger.info("Loading config settings")
    if "account_sid" not in twilio_settings or twilio_settings["account_sid"] == "":
        raise Exception("Twilio Account Sid is not defined.")
    else:
        twilio_account_sid = twilio_settings["account_sid"]
    if "auth_token" not in twilio_settings or twilio_settings["auth_token"] == "":
        raise Exception("Twilio Auth Token is not defined.")
    else:
        twilio_auth_token = twilio_settings["auth_token"]
    if "phone_number" not in twilio_settings or twilio_settings["phone_number"] == "":
        raise Exception("Twilio sandbox phone number is not defined.")
    else:
        twilio_sandbox_phone_number = twilio_settings["phone_number"]
    logger.info("Config settings loaded successfully")
    twilio_client = Client(twilio_account_sid, twilio_auth_token)

except Exception as e:
    logger.error(str(e))
    exit()

def notify_handover_volunteer(message, volunteer_number):
    message = twilio_client.messages.create(
        body=message,
        from_="whatsapp:{}".format(twilio_sandbox_phone_number),
        to="whatsapp:{}".format(volunteer_number)
    )

def notify_user(message, user_id):
    message = twilio_client.messages.create(
        body=message,
        to="whatsapp:{}".format("+" + user_id if not user_id.startswith("+") else user_id),
        from_ = "whatsapp:{}".format(twilio_sandbox_phone_number)
    )
