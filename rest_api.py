import json

from flask import Flask
from flask import request
from flask import Response
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from pycountry import languages
import logging
import configparser
from controllers import rule_controller
from controllers import mongo_controller
import os
from twilio.rest import Client
from textblob import TextBlob

logger = logging.getLogger("REST Server")
logger.setLevel(logging.INFO)
# create file handler which logs even debug messages
log_file_handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), "covid_chatbot.log"))
log_file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s,%(msecs)d - %(name)s - %(levelname)s - %(message)s")
log_file_handler.setFormatter(formatter)
logger.addHandler(log_file_handler)

# load configs from config.ini file
config = configparser.ConfigParser(inline_comment_prefixes="#")
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
default_settings = config["DEFAULT"]
twilio_settings = config["TWILIO"]

try:
    logger.info("Loading config settings")
    if "address" not in default_settings or default_settings["address"] == "":
        raise Exception("Server FQDN address is not defined.")
    else:
        server_address = default_settings["address"]
    if "port" not in default_settings or default_settings["port"] == "":
        server_port = None
    else:
        server_port = config.getint("DEFAULT", "port")
    if "binding" not in default_settings or default_settings["binding"] == "":
        binding = None
    else:
        binding = default_settings["binding"]
    if "swagger_file_path" not in default_settings or default_settings["swagger_file_path"] == "":
        raise Exception("Swagger file path is not defined.")
    else:
        swagger_file_path = default_settings["swagger_file_path"]
    if "swagger_url" not in default_settings or default_settings["swagger_url"] == "":
        raise Exception("Swagger URL is not defined.")
    else:
        swagger_url = default_settings["swagger_url"]
    if "account_sid" not in twilio_settings or twilio_settings["account_sid"] == "":
        raise Exception("Twilio Account Sid is not defined.")
    else:
        twilio_account_sid = twilio_settings["account_sid"]
    if "auth_token" not in twilio_settings or twilio_settings["auth_token"] == "":
        raise Exception("Twilio Auth Token is not defined.")
    else:
        twilio_auth_token = twilio_settings["auth_token"]
    logger.info("Config settings loaded successfully")
    twilio_client = Client(twilio_account_sid, twilio_auth_token)

except Exception as e:
    logger.error(str(e))
    exit()

if server_port is None:
    api_url = "{}/{}".format(server_address, swagger_file_path)
else:
    api_url = "{}:{}/{}".format(server_address, server_port, swagger_file_path)

swaggerui_blueprint = get_swaggerui_blueprint(
    swagger_url,
    api_url,
    config={  # Swagger UI config overrides
        "app_name": "COVID-19 Chatbot"
    },
)
app = Flask(__name__)
app.register_blueprint(swaggerui_blueprint, url_prefix=swagger_url)
CORS(app)


@app.route("/{}".format(swagger_file_path), methods=["GET"])  # endpoint to get/render yaml file in swagger UI
def get_swagger():
    """
    read and return swagger specification document
    :return: swagger document
    """
    yaml_document_file = open(os.path.join(os.path.dirname(__file__), swagger_file_path), "r")
    yaml_document = yaml_document_file.read()
    yaml_document_file.close()
    return Response(yaml_document, 200)


@app.route("/volunteer", methods=["POST"])
def add_hanover_volunteer():
    """
    add volunteer for handovering the conversation
    :return: json object/error HTTP response
    """
    try:
        content_type = request.content_type
        if "form-" in content_type:
            for key in request.form.keys():
                print("{}:{}".format(key, request.form[key]))
            full_name = request.form["full_name"]
            phone_number = request.form["phone_number"]
            languages = request.form["languages"]
            if "," in languages:
                languages = languages.split(",")
            if len(full_name) == 0 or len(phone_number) == 0 or len(languages) == 0:
                raise Exception("phone number or/and languages are empty!")
            result = mongo_controller.add_handover_volunteer(full_name, phone_number, languages)
            return Response(json.dumps({"message": result}), 200, mimetype="application/json")
    except Exception as err:
        logger.error(str(err))
        return Response(json.dumps(err), 400, mimetype="application/json")


@app.route("/ask", methods=["POST"])
def get_question_answer():
    """
    get answer for a given question
    :return: json object/error HTTP response
    """
    try:
        content_type = request.content_type
        if "form-" in content_type:
            # for key in request.form.keys():
            #     print("{}:{}".format(key, request.form[key]))
            message = request.form["Body"]
            num_media = 0
            if "NumMedia" in request.form.keys():
                num_media = request.form["NumMedia"]  # check if user sent any media msg (e.g. voice, picture)
            if len(message) == 0 and int(num_media) > 0:
                message = twilio_client.messages.create(
                    body="Sorry, I can only answer to textual messages at the moment! 😉🧐",
                    from_=request.form["To"],
                    to=request.form["From"],
                )

            user_id = request.form["From"].replace("whatsapp:", "")
        if len(
                message) > 2:  # if the length of message is more than 2 characters then check the language; TextBlob library requires a sentence/word with at least 3 characters to detect a language
            blob = TextBlob(message)
            query_language = blob.detect_language()
            if query_language is not None:
                lang_name = languages.get(alpha_2=query_language)
                if lang_name is None:
                    result = "I don't understand your language 🧐"
                else:
                    if lang_name.name == "English":
                        result = rule_controller.answer_question(user_id, message)
                    else:
                        result = "I can only talk in *English* 🇬🇧 at the moment, but soon I will be able to talk in _{}_ 😎".format(
                            lang_name.name)
            else:
                result = "I don't understand your language 🧐"
        else:
            result = rule_controller.answer_question(user_id, message)

        if result is not None:  # in case of handovering user's question to a human, we do not return anything here
            message = twilio_client.messages.create(
                body=result,
                from_=request.form["To"],
                to=request.form["From"],
            )
        return "OK"  # this is to fix the "The view function did not return a valid response" error as we do not return a Response to twilio api, we use twilio library instead.
    except Exception as err:
        logger.error(str(err))
        message = twilio_client.messages.create(
            body="Oops! Something wrong happened on my side!",
            from_=request.form["To"],
            to=request.form["From"],
        )
        return "Not OK!"


if __name__ == "__main__":
    try:
        if binding is not None and server_port is not None:
            app.run(host=binding, port=server_port, threaded=True, debug=True)
        elif server_port is not None:
            app.run(port=server_port, threaded=True, debug=True)
        elif binding is not None:
            app.run(host=binding, threaded=True, debug=True)
        else:
            app.run(threaded=True, debug=True)
    except Exception as e:
        logger.error(str(e))
        exit()
