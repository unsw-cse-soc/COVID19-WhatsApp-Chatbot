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
        "phone_number": "{}".format("+" + phone_number if not phone_number.startswith("+") else phone_number),
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
    query_result = db.COVIDChatbot_Misconduct.find_one({"phone_number": "{}".format("+" + phone_number if not phone_number.startswith("+") else phone_number)})
    if query_result is not None:
        return query_result
    return None


def get_handover_volunteers():
    """
    get list of volunteers to answer users' queries (handover phone numbers, and language they can speak)
    :return: list of volunteers, None if no volunteer registered
    """
    db = mongo_client.COVIDChatbot_HandoverNumbers
    query_result = db.COVIDChatbot_HandoverNumbers.find()
    if query_result is not None:
        return list(query_result)
    return None


def get_handover_volunteers_by_language(language):
    """
    get list of volunteers to answer users' queries for given language
    :return: list of volunteers, None if no volunteer registered
    """
    db = mongo_client.COVIDChatbot_HandoverNumbers
    query_result = db.COVIDChatbot_HandoverNumbers.find({"languages": language})
    if query_result is not None:
        return list(query_result)
    return None


def get_volunteer_details(phone_number):
    """
    get volunteer's details
    :param phone_number: volunteer's phone number
    :return: volunteer as object, None if volunteer's number does not exist
    """
    db = mongo_client.COVIDChatbot_HandoverNumbers
    query_result = db.COVIDChatbot_HandoverNumbers.find_one({"phone_number": "{}".format("+" + phone_number if not phone_number.startswith("+") else phone_number)})
    if query_result is not None:
        return query_result
    return None


def add_handover_volunteer(full_name, phone_number, languages):
    """
    add a volunteer to the handover list
    :param full_name: volunteer's first name and last name
    :param phone_number: volunteer's phone number
    :param languages: language(s) the person can speak (answer users' queries) - used for matching purposes
    :return: True if the operation is successful, None if an error happens
    """
    if get_volunteer_details(phone_number) is None:
        db = mongo_client.COVIDChatbot_HandoverNumbers
        handover_request_details = {
            "full_name": full_name,
            "phone_number": "{}".format("+" + phone_number if not phone_number.startswith("+") else phone_number),
            "languages": languages,
            "num_users_answered": 0
        }
        collection = db.COVIDChatbot_HandoverNumbers.insert_one(handover_request_details)
        if str(collection.inserted_id) != "":  # if the request is successfully added to the database
            return "Volunteer id: {}".format(str(collection.inserted_id))
        return None
    else:
        return "This number is already registered to the list of volunteers!"


def add_handover_request(user_phone_number, language):
    """
    add user's handover request to the waiting list
    :param user_phone_number: user phone number
    :param language: language of user
    :return: True if the operation is successful, None if an error happens
    """
    handover_request = get_handover_request(user_phone_number) # check to see if any handover request from the user is still in the stack
    if handover_request is None:
        db = mongo_client.COVIDChatbot_HandoverRequests
        handover_request_details = {
            "user_number": "{}".format("+" + user_phone_number if not user_phone_number.startswith("+") else user_phone_number),
            "language": language,
            "volunteer_number": None,
            "status": "WAITING"
        }
        collection = db.COVIDChatbot_HandoverRequests.insert_one(handover_request_details)
        if str(collection.inserted_id) != "":  # if the request is successfully added to the database
            return str(collection.inserted_id)
    else:
        return str(handover_request["_id"])


def accept_handover_request(user_phone_number, handovered_phone_number):
    """
    add user's handover request to the waiting list
    :param user_phone_number: user phone number
    :param handovered_phone_number: phone number of person who accepted to answer user's queries
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_HandoverRequests
    query_result = db.COVIDChatbot_HandoverRequests.update_one({"user_number": "{}".format("+" + user_phone_number if not user_phone_number.startswith("+") else user_phone_number)},
                                                               {
                                                                   "$set": {
                                                                       "volunteer_number": "{}".format("+" + handovered_phone_number if not handovered_phone_number.startswith("+") else handovered_phone_number),
                                                                       "status": "OPEN"
                                                                   }
                                                               },
                                                               upsert=False)
    if query_result.modified_count > 0:
        return True
    return False


def close_handover_request(user_phone_number):
    """
    close user's handover request
    :param user_phone_number: user phone number
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_HandoverRequests
    query_result = db.COVIDChatbot_HandoverRequests.update_one({"user_number": "{}".format("+" + user_phone_number if not user_phone_number.startswith("+") else user_phone_number)},
                                                               {
                                                                   "$set": {
                                                                       "status": "CLOSE"
                                                                   }
                                                               },
                                                               upsert=False)
    if query_result.modified_count > 0:
        return True
    return False


def reopen_handover_request(user_phone_number):
    """
    reopen user's handover request
    :param user_phone_number: user phone number
    :return: True if the operation is successful, False if an error happens
    """
    db = mongo_client.COVIDChatbot_HandoverRequests
    query_result = db.COVIDChatbot_HandoverRequests.update_one({"user_number": "{}".format("+" + user_phone_number if not user_phone_number.startswith("+") else user_phone_number)},
                                                               {
                                                                   "$set": {
                                                                       "status": "OPEN"
                                                                   }
                                                               },
                                                               upsert=False)
    if query_result.modified_count > 0:
        return True
    return False


def get_handover_request(user_phone_number):
    """
    get user handover request
    :param user_phone_number: user phone number
    :return: user request object if phone number exist, None if phone  number does not exist
    """
    db = mongo_client.COVIDChatbot_HandoverRequests
    query_result = db.COVIDChatbot_HandoverRequests.find_one({
        "$and": [
            {"user_number": "{}".format("+" + user_phone_number if not user_phone_number.startswith("+") else user_phone_number)},
            {
                "$or": [{"status": "WAITING"},
                        {'status': "OPEN"}]
            }
        ]
    })
    if query_result is not None:
        return query_result
    return None
