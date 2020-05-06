import logging
import configparser
from pymongo import MongoClient
from bson import ObjectId
import os

logger = logging.getLogger("MongoDB Controller")
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
db_settings = config["MONGODB"]

try:
    logging.info("Loading config settings")
    if "username" not in db_settings or db_settings["username"] == "":
        db_username = None
        logging.warning("Mongodb username is not defined.")
    else:
        db_username = db_settings["username"]
    if "password" not in db_settings or db_settings["password"] == "":
        db_password = None
        logging.warning("Mongodb password is not defined.")
    else:
        db_password = db_settings["password"]
    if "port" not in db_settings or db_settings["port"] == "":
        raise Exception("Mongodb port is not defined.")
    else:
        db_port = db_settings["port"]
    if "address" not in db_settings or db_settings["address"] == "":
        raise Exception("Mongodb address is not defined.")
    else:
        db_address = db_settings["address"]
    logging.info("Config settings loaded successfully")

except Exception as e:
    logging.error(str(e))
    exit()

if db_username and db_password:
    mongo_client = MongoClient("{}:{}".format(db_address, db_port), username=db_username, password=db_password)
elif db_username is None and db_password is None:
    mongo_client = MongoClient("{}:{}".format(db_address, db_port))
else:
    logging.error(str(Exception(
        "There is an problem MONGODB section of config.ini file, either username or password is not defined")))
    exit()


def add_topic(name, subtopics, keywords):
    """
    add new topic into db
    :param name: name of topic
    :param subtopics: subtopics under the topic
    :param keywords: keywords under the topic
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_Topics
    topic_details = {
        "name": name,
        "subtopics": subtopics,
        "keywords": keywords,
    }
    collection = db.COVIDChatbot_Topics.insert_one(topic_details)
    if str(collection.inserted_id) != "":  # if the request is successfully added to the database
        return str(collection.inserted_id)
    return None


def add_subtopic(name, questions_answers, keywords):
    """
    add new subtopic into db
    :param name
    :param questions_answers
    :param keywords
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_Subtopics
    subtopic_details = {
        "name": name,
        "questions_answers": questions_answers,
        "keywords": keywords,
    }
    collection = db.COVIDChatbot_Subtopics.insert_one(subtopic_details)
    if str(collection.inserted_id) != "":  # if the request is successfully added to the database
        return str(collection.inserted_id)
    return None


def add_question_answer(question, answer, more_details, keywords):
    """
    add new question/answer into db
    :param question: question
    :param answer: answer for the question
    :param more_details: more details including links, videos, etc
    :param keywords: keywords of the question
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_QAs
    subtopic_details = {
        "question": question,
        "answer": answer,
        "keywords": keywords,
        "more_details": more_details,
    }
    collection = db.COVIDChatbot_QAs.insert_one(subtopic_details)
    if str(collection.inserted_id) != "":  # if the request is successfully added to the database
        return str(collection.inserted_id)
    return None


def get_topics():
    """
    get list of topics
    :return: topics object
    """
    db = mongo_client.COVIDChatbot_Topics
    query_result = db.COVIDChatbot_Topics.find()
    if query_result is not None:
        return list(query_result)
    return None


def get_topic(id):
    """
    find topic with given id
    :param id: id of topic
    :return: topic object if the id, None if topic does not exist
    """
    db = mongo_client.COVIDChatbot_Topics
    query_result = db.COVIDChatbot_Topics.find_one({"_id": ObjectId(str(id))})
    if query_result is not None:
        return query_result
    return None


def get_subtopic(id):
    """
    find subtopic with given id
    :param id: id of subtopic
    :return: subtopic object if the id, None if subtopic does not exist
    """
    db = mongo_client.COVIDChatbot_Subtopics
    query_result = db.COVIDChatbot_Subtopics.find_one({"_id": ObjectId(str(id))})
    if query_result is not None:
        return query_result
    return None


def get_question_answer(id):
    """
    find topic with given id
    :param id: id of question/answer
    :return: question/answer object if the id, None if topic does not exist
    """
    db = mongo_client.COVIDChatbot_QAs
    query_result = db.COVIDChatbot_QAs.find_one({"_id": ObjectId(str(id))})
    if query_result is not None:
        return query_result
    return None


def update_topic(id, subtopics=None, keywords=None):
    """
    update topic
    :param id
    :param subtopics
    :param keywords
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_Topics
    if subtopics is not None and keywords is not None:
        query_result = db.COVIDChatbot_Topics.update_one({"_id": ObjectId(str(id))},
                                                         {
                                                             "$set": {
                                                                 "subtopics": subtopics,
                                                                 "keywords": keywords,
                                                             }
                                                         },
                                                         upsert=False)
    elif subtopics is not None:
        query_result = db.COVIDChatbot_Topics.update_one({"_id": ObjectId(str(id))},
                                                         {
                                                             "$set": {
                                                                 "subtopics": subtopics,
                                                             }
                                                         },
                                                         upsert=False)

    elif keywords is not None:
        query_result = db.COVIDChatbot_Topics.update_one({"_id": ObjectId(str(id))},
                                                         {
                                                             "$set": {
                                                                 "keywords": keywords,
                                                             }
                                                         },
                                                         upsert=False)
    if query_result.modified_count > 0:
        return True
    return False


def update_subtopic(id, questions_answers=None, keywords=None):
    """
    update subtopic
    :param id
    :param questions_answers
    :param keywords
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_Subtopics
    if questions_answers is not None and keywords is not None:
        query_result = db.COVIDChatbot_Subtopics.update_one({"_id": ObjectId(str(id))},
                                                            {
                                                                "$set": {
                                                                    "questions_answers": questions_answers,
                                                                    "keywords": keywords,
                                                                }
                                                            },
                                                            upsert=False)
    elif questions_answers is not None:
        query_result = db.COVIDChatbot_Subtopics.update_one({"_id": ObjectId(str(id))},
                                                            {
                                                                "$set": {
                                                                    "questions_answers": questions_answers,
                                                                }
                                                            },
                                                            upsert=False)

    elif keywords is not None:
        query_result = db.COVIDChatbot_Subtopics.update_one({"_id": ObjectId(str(id))},
                                                            {
                                                                "$set": {
                                                                    "keywords": keywords,
                                                                }
                                                            },
                                                            upsert=False)
    if query_result.modified_count > 0:
        return True
    return False


def add_user_to_blacklist(phone_number):
    """
    add user number to the blacklist, this user misbehaved
    :param phone_number: user phone number
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_Misconduct
    user_details = {
        "phone_number": phone_number,
    }
    collection = db.COVIDChatbot_Misconduct.insert_one(user_details)
    if str(collection.inserted_id) != "":  # if the request is successfully added to the database
        return str(collection.inserted_id)
    return False

def check_user_in_blacklist(phone_number):
    """
    check if user is in the blacklist
    :param phone_number: user phone number
    :return: user object if the id, None if user does not exist
    """
    db = mongo_client.COVIDChatbot_Misconduct
    query_result = db.COVIDChatbot_Misconduct.find_one({"phone_number": phone_number})
    if query_result is not None:
        return query_result
    return None