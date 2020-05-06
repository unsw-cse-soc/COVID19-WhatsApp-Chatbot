import requests
import os
import logging
import configparser
import re

logger = logging.getLogger("NLP Controller")
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
stanford_nlp_settings = config["STANFORD_CORNLP"]

try:
    logging.info("Loading config settings")
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

with open(os.path.join(os.path.dirname(__file__), "..", "utils/english_stopwords.txt"), "r") as myfile:
    english_stopwords = myfile.read().split(",")


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
