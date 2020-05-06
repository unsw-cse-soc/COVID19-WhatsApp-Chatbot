import logging
import configparser
import os
import re

import requests
from pymongo import MongoClient
from bson import ObjectId
import pandas as pd

logging.basicConfig(filename="mongodb_populate_output.log", filemode="a",
                    format="%(asctime)s,%(msecs)d %(name)s - %(levelname)s - %(message)s",
                    datefmt="%d-%b-%y %H:%M:%S",
                    level=logging.INFO)

# load configs from config.ini file
config = configparser.ConfigParser(inline_comment_prefixes="#")
config.read(os.path.join(os.path.dirname(__file__), "..", "config.ini"))
default_settings = config["DEFAULT"]
stanford_nlp_settings = config["STANFORD_CORNLP"]
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
    if "address" not in stanford_nlp_settings or stanford_nlp_settings["address"] == "":
        raise Exception("Stanford CoreNLP server address is not defined.")
    else:
        nlp_server_address = stanford_nlp_settings["address"]
    if "port" not in stanford_nlp_settings or stanford_nlp_settings["port"] == "":
        nlp_server_port = None
        logging.warning("Stanford CoreNLP server port is not defined.")
    else:
        nlp_server_port = stanford_nlp_settings["port"]
    if "path" not in stanford_nlp_settings or stanford_nlp_settings["path"] == "":
        raise Exception("Stanford CoreNLP server path is not defined.")
    else:
        nlp_server_path = stanford_nlp_settings["path"]
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

with open(os.path.join(os.getcwd(), "../utils/english_stopwords.txt"), "r") as myfile:
    english_stopwords = myfile.read().split(",")


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


def __post_request_nlpserver(query):
    """
    Send HTTP POST request to NLP server with json body
    :return: json formatted result
    """
    # first, concatenate all sentences
    if isinstance(query, str):
        query = query.replace(".", " ").replace("(", "").replace(")", "").replace(",", " ")
    else:
        query = query.decode("utf-8").replace(".", " ").replace("(", "").replace(")", "").replace(",", " ")
    if nlp_server_address and nlp_server_port:
        # second, call the nlp server
        nlp_server_response = requests.post("{}:{}{}".format(nlp_server_address, nlp_server_port, nlp_server_path),
                                            data=query)
    else:
        # second, call the nlp server
        nlp_server_response = requests.post("{}{}".format(nlp_server_address, nlp_server_path), data=query)
    if nlp_server_response.status_code != 200:
        raise Exception(nlp_server_response.content)
    return nlp_server_response.json()


def extract_special_characters(query):
    regex = r"(\w|\s)*"
    matches = re.finditer(regex, query, re.DOTALL)
    newstr = ''
    for matchNum, match in enumerate(matches):
        matchNum = matchNum + 1
        newstr = newstr + match.group()
    return newstr


def extract_keywords(query):
    """
    Extract keywords from given input query
    :param query: a sentence/string
    :return: list of keywords
    """
    nlp_server_response = __post_request_nlpserver(extract_special_characters(query))
    keywords = []

    for sentence in nlp_server_response['sentences']:
        for token in sentence['tokens']:
            if token['pos'] in {'NN', 'JJ', 'NNP', 'NNS', 'NNPS', 'VB', 'VBN', 'VBZ', 'VBP', 'VBG'}:
                if not token["lemma"].lower() in english_stopwords:
                    if not token['lemma'] in {'be', 'have'}:
                        keywords.append(token['lemma'])
    return keywords


def annotate_expression(expression):
    nlp_server_response = __post_request_nlpserver(extract_special_characters(expression).lower().replace('?', ''))
    return nlp_server_response['sentences'][0]['tokens']


def add_rule(topic, annotated_question, answer):
    pattern = generate_pattern(annotated_question)
    # found = check_pattern(topic, pattern)
    found = False
    if found:
        return False
    else:
        output = add_pattern(topic, pattern, answer)
        return output


def generate_pattern(annotated_expression):
    rule = []
    for tokenItem in annotated_expression:
        if tokenItem['pos'] in {'MD', 'PRP', 'PRP$', 'RB'}:
            rule.append('[*]')
        elif tokenItem['pos'] in {'VBP'} and tokenItem['lemma'] in {'have', 'has', 'had'}:
            rule.append('[*]')
        elif tokenItem['pos'] in {'VBZ', 'DT', 'VBP', 'TO'}:
            rule.append('[%s]' % tokenItem['word'])
        elif tokenItem['pos'] in {'WP', 'WDT', 'WRB'}:
            rule.append('[*] %s' % tokenItem['word'])
        else:
            if len(tokenItem['word'].split('/')) > 1:
                rule.append('(%s)' % '|'.join(tokenItem['word'].split('/')))
            elif (tokenItem['pos'] not in {'.', ',', ':', "''", "``"}) and (not tokenItem['word'] == '&'):
                rule.append(tokenItem['word'].replace('&', '').strip())
    generated_pattern = (' '.join(rule)).lower().replace('-', '')
    return generated_pattern


def check_pattern(topic, pattern):
    try:
        datafile = open("../brain/rules/%s.rive" % topic)
        found = False
        for line in datafile:
            if '+ %s' % pattern in line:
                found = True
                # print 'found'
                break
        return found
    except IOError as ie:
        return False


def add_pattern(topic, pattern, answer):
    with open("../brain/rules/%s.rive" % topic.lower().replace(" ", "_"), "a") as myfile:
        myfile.write("+ %s\n" % pattern)
        myfile.write("- %s\n\n" % answer)
    return True


def import_rules():
    topic = "COVID-19"
    # subtopics = ["General questions", "Questions about mask"]
    training_data_file = "Completed_Topic_COVID-19-Language-English.xlsx"
    dfs = pd.read_excel("./Training-Data/{}".format(training_data_file), sheet_name=None)
    subtopics = dfs.keys()
    subtopics_ids = []
    subtopics_keywords = []
    for subtopic in subtopics:
        subtopic_qas_ids = []
        subtopic_keywords = []
        for index, row in dfs[subtopic].iterrows():
            if isinstance(row["Links"], str):
                if '\n' in row["Links"]:
                    more_details = [link for link in row['Links'].split("\n") if len(link) > 5]
                else:
                    if len(row["Links"]) > 5:
                        more_details = [row["Links"]]
            else:
                more_details = []

            question_keywords = list(set(map(lambda keyword: keyword.lower(), extract_keywords(row["Questions"]))))
            if isinstance(row["Paraphrases"], str):
                for paraphrased_question in row["Paraphrases"].split("\n"):
                    question_keywords = question_keywords + list(
                        set(map(lambda keyword: keyword.lower(), extract_keywords(paraphrased_question))))

            qa_id = add_question_answer(question=row["Questions"], answer=row["Answers"], more_details=more_details,
                                        keywords=list(set(question_keywords)))
            add_rule(subtopic.lower().replace(" ", "_"), annotate_expression(row["Questions"]), qa_id)
            if isinstance(row["Paraphrases"], str):
                for paraphrased_question in row["Paraphrases"].split("\n"):
                    # question_keywords = question_keywords + list(set(map(lambda keyword: keyword.lower(), extract_keywords(paraphrased_question))))
                    # qa_id = add_question_answer(question=paraphrased_question, answer=row["Answers"], more_details=more_details,
                    #                             keywords=question_keywords)
                    add_rule(subtopic.lower().replace(" ", "_"), annotate_expression(paraphrased_question), qa_id)
                    # subtopic_qas_ids.append(qa_id)
            subtopic_qas_ids.append(qa_id)
            subtopic_keywords = list(set(subtopic_keywords + question_keywords))
        subtopic_id = add_subtopic(subtopic, subtopic_qas_ids, subtopic_keywords)
        subtopics_ids.append(subtopic_id)
        subtopics_keywords = list(set(subtopics_keywords + subtopic_keywords))
    add_topic(topic, subtopics_ids, subtopics_keywords)


if __name__ == "__main__":
    import_rules()
