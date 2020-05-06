import os
import logging
import inflect
import uuid
import configparser
from rivescript import RiveScript
from controllers import mongo_controller
from controllers import nlp_controller
from controllers import handover_controller

logger = logging.getLogger("Rule Controller")
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
whatsapp_settings = config["WHATSAPP"]

try:
    logger.info("Loading config settings")
    if "phone_number" not in whatsapp_settings or whatsapp_settings["phone_number"] == "":
        raise Exception("Human phone number for conversation handover purposes is not defined.")
    else:
        human_phone_number = whatsapp_settings["phone_number"]
    logger.info("Config settings loaded successfully")

except Exception as e:
    logger.error(str(e))
    exit()

# load number to word converter
num2word = inflect.engine()

bot = RiveScript()
bot.load_directory(
    os.path.join(os.path.dirname(__file__), "..", "brain/rules")
)
bot.sort_replies()


def __generate_rule_pattern(annotated_expression):
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


def __check_rule_pattern(topic, pattern):
    try:
        datafile = open(os.path.join(os.path.dirname(__file__), "..", "brain/rules", "%s.rive" % topic))
        found = False
        for line in datafile:
            if '+ %s' % pattern in line:
                found = True
                # print 'found'
                break
        return found
    except IOError as ie:
        return False


def __add_temporary_conversational_rule(topic,
                                        annotated_user_question,
                                        chatbot_question,
                                        main_conversation_id,
                                        subtopic_conversation_id,
                                        conditions):
    if annotated_user_question is not None:
        rule_pattern = __generate_rule_pattern(annotated_user_question)
        is_pattern_exist = __check_rule_pattern(topic, rule_pattern)
        if is_pattern_exist:  # rule is already added
            return False
    else:
        rule_pattern = None

    with open(os.path.join(os.path.dirname(__file__), "..", "brain/rules", "%s.rive" % topic), "a") as myfile:
        if rule_pattern is not None:
            myfile.write("+ %s\n" % rule_pattern)
            myfile.write("- %s {topic=%s}\n\n" % (chatbot_question, subtopic_conversation_id))

        if conditions is not None:
            myfile.write("> topic %s\n\n" % subtopic_conversation_id)
            for condition in conditions:
                myfile.write("  + %s \n" % condition['user_answer'])
                myfile.write("  - ^Recursive=%s\n\n" % condition['chatbot_answer'])

            myfile.write("  + *\n")
            myfile.write("  - ^Return-to-Maintopic=<star>{topic=%s}\n\n" % main_conversation_id)

            myfile.write("< topic\n\n")

    return True


def suggest_topics(query):
    query_keywords = nlp_controller.extract_keywords(query)
    if query_keywords:
        query_keywords = list(set(query_keywords))  # remove duplications
        if query_keywords:
            topics = mongo_controller.get_topics()
            candidate_topics = []
            for topic in topics:
                matched_keywords = 0
                for keyword in query_keywords:
                    if keyword.lower() in topic["keywords"]:
                        matched_keywords += 1
                if matched_keywords > 0:
                    candidate_topics.append(
                        {"matched_keywords_ratio": round((float(matched_keywords) / len(query_keywords)), 2),
                         "name": topic["name"],
                         "id": str(topic["_id"])})
            if candidate_topics:
                most_similar_topic = max(candidate_topics, key=lambda topic: topic["matched_keywords_ratio"])
                if most_similar_topic["matched_keywords_ratio"] != 0.0:
                    selected_topics = [most_similar_topic]
                    for topic in candidate_topics:
                        if topic["matched_keywords_ratio"] == most_similar_topic["matched_keywords_ratio"] and topic[
                            "id"] != most_similar_topic["id"]:
                            selected_topics.append(topic)
                    return selected_topics, query_keywords
    return None, None


def suggest_subtopics(topics, query_keywords):
    candidate_subtopics = []
    for topic in topics:
        topic_object = mongo_controller.get_topic(topic["id"])
        for subtopic_id in topic_object["subtopics"]:
            matched_keywords = 0
            subtopic_object = mongo_controller.get_subtopic(subtopic_id)
            for keyword in query_keywords:
                if keyword.lower() in subtopic_object["keywords"]:
                    matched_keywords += 1
            if matched_keywords > 0:
                candidate_subtopics.append(
                    {"matched_keywords_ratio": round((float(matched_keywords) / len(query_keywords)), 2),
                     "subtopic_name": subtopic_object["name"],
                     "subtopic_id": subtopic_id,
                     "topic_name": topic["name"],
                     "topic_id": topic["id"]})
    if candidate_subtopics:
        most_similar_subtopic = max(candidate_subtopics, key=lambda subtopic: subtopic["matched_keywords_ratio"])
        if most_similar_subtopic["matched_keywords_ratio"] != 0.0:
            selected_subtopics = [most_similar_subtopic]
            for subtopic in candidate_subtopics:
                if subtopic["matched_keywords_ratio"] == most_similar_subtopic["matched_keywords_ratio"] and \
                        subtopic[
                            "subtopic_id"] != most_similar_subtopic["subtopic_id"]:
                    selected_subtopics.append(subtopic)
            return selected_subtopics, query_keywords
    return None


def suggest_questions(subtopics, query_keywords):
    candidate_questions = []
    for subtopic in subtopics:
        subtopic_object = mongo_controller.get_subtopic(subtopic["subtopic_id"])
        for qa_id in subtopic_object["questions_answers"]:
            matched_keywords = 0
            question_answer_object = mongo_controller.get_question_answer(qa_id)
            for keyword in query_keywords:
                if keyword.lower() in question_answer_object["keywords"]:
                    matched_keywords += 1
            if matched_keywords > 0:
                candidate_questions.append(
                    {"matched_keywords_ratio": round((float(matched_keywords) / len(query_keywords)), 2),
                     "question_text": question_answer_object["question"],
                     "question_id": qa_id,
                     "subtopic_name": subtopic["subtopic_name"],
                     "subtopic_id": subtopic["subtopic_id"],
                     "topic_name": subtopic["topic_name"],
                     "topic_id": subtopic["topic_id"]})
    if candidate_questions:
        most_similar_question = max(candidate_questions, key=lambda question: question["matched_keywords_ratio"])
        if most_similar_question["matched_keywords_ratio"] != 0.0:
            selected_questions = [most_similar_question]
            for question in candidate_questions:
                if question["matched_keywords_ratio"] == most_similar_question["matched_keywords_ratio"] and \
                        question[
                            "question_id"] != most_similar_question["question_id"]:
                    selected_questions.append(question)
            return selected_questions
    return None


def find_suggestions(query):
    suggested_topics, query_keywords = suggest_topics(query)
    if suggested_topics:
        suggested_subtopics, query_keywords = suggest_subtopics(suggested_topics, query_keywords)
        if not suggested_subtopics:
            return {
                "confused": True,
                "topics": suggested_topics,
                "subtopics": [],
                "questions": []
            }
        else:
            suggested_questions = suggest_questions(suggested_subtopics, query_keywords)
            if not suggested_questions:
                return {
                    "confused": True,
                    "topics": suggested_topics,
                    "subtopics": suggested_subtopics,
                    "questions": []
                }
        if len(suggested_topics) > 1 or len(suggested_subtopics) > 1:
            return {
                "confused": True,
                "topics": suggested_topics,
                "subtopics": suggested_subtopics,
                "questions": suggested_questions
            }

        return {
            "confused": False,
            "topics": suggested_topics,
            "subtopics": suggested_subtopics,
            "questions": suggested_questions
        }
    else:
        return {
            "confused": True,
            "topics": [],
            "subtopics": [],
            "questions": []
        }


def answer_question(user_id, query):
    suggestion = False  # indicator that shows chatbot found some similar questions to the given user question
    confusion = False  # indicator that shows chatbot is confused between two or more subtopics for the given user question
    chatbot_response = None

    # TODO check whether user is in the blacklist because of misbehaviour
    # output_result = mongo_controller.check_user_in_blacklist(user_id.replace("+", "")) # check if user phone number is in the blacklist because of misbehaviour
    # if output_result is not None:
    #     return "Unfortunately, I'm not allowed to talk to you...😔"
    bot.load_directory(
        os.path.join(os.path.dirname(__file__), "..", "brain/rules")
    )
    bot.sort_replies()
    reply = bot.reply(user_id, query)

    # first check, if user's reply is another question, it's not any of the shown options (suggested questions, subtopics)
    while reply.startswith(
            "^Return-to-Maintopic="):  # pass the question to the upper *topic(s)* in generated conversation rules
        recursive_question = reply.split("^Return-to-Maintopic=")[1]
        reply = bot.reply(user_id, recursive_question)  # ask the question again

    if reply.startswith("^Recursive="):  # reply is a chosen option
        recursive_question = reply.split("^Recursive=")[1]
        if "(*)" not in reply:
            recursive_topic = bot.get_uservar(user_id, "topic")
            bot.set_uservar(user_id, "topic", "random")
            reply = bot.reply(user_id,
                              recursive_question)  # ask bot the question associated to the option chosen by user
            bot.set_uservar(user_id, "topic", recursive_topic)
        else:
            reply = recursive_question

    if "No Reply" in reply:  # if chatbot cannot match any pattern with user question
        suggestion_result = find_suggestions(query)  # check for any suggestion (subtopics, questions)

        # check if the chatbot found two or more relevant subtopics for the question asked by user
        if suggestion_result["confused"]:
            # if the question is successfully matched with the topic (COVID-19), meaning that user cannot ask something questions about other topics that the chatbot is not designed for.
            if len(suggestion_result["topics"]) > 0:
                topic_object = None  # we only have one topic "COVID-19"
                for question in suggestion_result["questions"]:
                    if topic_object is None:
                        subtopic = {
                            "id": question["subtopic_id"],
                            "name": question["subtopic_name"],
                            "questions": [question["question_text"]]
                        }
                        topic_object = {
                            "id": question["topic_id"],
                            "name": question["topic_name"],
                            "subtopics": [subtopic]
                        }
                    else:
                        subtopic_found = False
                        for subtopic in topic_object['subtopics']:
                            if subtopic["id"] == question["subtopic_id"]:
                                subtopic_found = True
                                if question["question_text"] not in subtopic["questions"]:
                                    subtopic["questions"].append(question["question_text"])
                        if not subtopic_found:
                            subtopic = {
                                "id": question["subtopic_id"],
                                "name": question["subtopic_name"],
                                "questions": [question["question_text"]]
                            }
                            topic_object['subtopics'].append(subtopic)

                if topic_object is not None:  # if we have a root branch (topic) - because this chatbot is designed for "COVID-19" topic, therefore we only have one topic
                    main_conversation_id = None
                    if len(topic_object["subtopics"]) > 1:
                        chatbot_question = "#*#".join(
                            ["{}. {}".format(index + 1, subtopic["name"]) for
                             index, subtopic in
                             enumerate(topic_object["subtopics"])][:3])
                        chatbot_question = "{}#*#{}. Talk to human".format(chatbot_question,
                                                                           len(topic_object["subtopics"]) + 1)
                        main_conversation_id = "choose_subtopic_{}".format(str(uuid.uuid4()))

                        __add_temporary_conversational_rule(
                            topic="live_conversations",
                            annotated_user_question=nlp_controller.annotate_expression(query),
                            chatbot_question=chatbot_question,
                            main_conversation_id="random",
                            subtopic_conversation_id=main_conversation_id,
                            conditions=None
                        )

                    main_conversation_conditions = []
                    for subtopic_index, subtopic in enumerate(topic_object["subtopics"][:3]):
                        subtopic_conversation_conditions = []
                        subtopic_conversation_id = "choose_question_{}".format(str(uuid.uuid4()))

                        if len(subtopic["questions"]) > 1:
                            chatbot_subtopic_question = "(*)".join(
                                ["{}. {}".format(index + 1, question_answer) for
                                 index, question_answer in
                                 enumerate(subtopic["questions"])][:4])
                            # chatbot_subtopic_question = "{}(*){}. Talk to human".format(chatbot_subtopic_question,
                            #                                                             len(subtopic["questions"]) + 1)
                        else:
                            chatbot_subtopic_question = "{}. {}(*)".format(1,
                                                                           subtopic["questions"][0])
                            # chatbot_subtopic_question = "{}{}. Talk to human".format(chatbot_subtopic_question,
                            #                                                          len(subtopic["questions"]) + 1)

                        for question_index, question in enumerate(subtopic["questions"][:4]):
                            subtopic_conversation_conditions.append(
                                {"user_answer": "[*]({}|{})[*]".format(question_index + 1,
                                                                       num2word.number_to_words(question_index + 1)),
                                 "chatbot_answer": question})

                        # add option for talk to human
                        # subtopic_conversation_conditions.append(
                        # {"user_answer": "[*]({}|{})[*]".format(len(subtopic["questions"]) + 1,
                        #                                        num2word.number_to_words(
                        #                                            len(subtopic["questions"]) + 1)),
                        #  "chatbot_answer": "%s {topic=%s}" % ("Talk to human",
                        #                                       "random")})

                        __add_temporary_conversational_rule(
                            topic="live_conversations",
                            annotated_user_question=None,
                            chatbot_question=None,
                            main_conversation_id=main_conversation_id,
                            subtopic_conversation_id=subtopic_conversation_id,
                            conditions=subtopic_conversation_conditions
                        )

                        main_conversation_conditions.append(
                            {"user_answer": "[*]({}|{}|{})[*]".format(subtopic_index + 1,
                                                                      num2word.number_to_words(subtopic_index + 1),
                                                                      subtopic["name"].lower()
                                                                      ),
                             "chatbot_answer": "%s {topic=%s}" % (chatbot_subtopic_question,
                                                                  subtopic_conversation_id)})

                    main_conversation_conditions.append(
                        {"user_answer": "[*]({}|{}|{})[*]".format(len(topic_object["subtopics"]) + 1,
                                                                  num2word.number_to_words(
                                                                      len(topic_object["subtopics"]) + 1),
                                                                  "talk to human|talk to person"
                                                                  ),
                         "chatbot_answer": "%s {topic=%s}" % ("Talk to human",
                                                              "user_initiate_handover")})
                    if main_conversation_id is not None:
                        __add_temporary_conversational_rule(
                            topic="live_conversations",
                            annotated_user_question=None,
                            chatbot_question=None,
                            main_conversation_id="random",
                            subtopic_conversation_id=main_conversation_id,
                            conditions=main_conversation_conditions
                        )

                    bot.load_directory(
                        os.path.join(os.path.dirname(__file__), "..", "brain/rules")
                    )

                    bot.sort_replies()
                    reply = bot.reply(user_id, query)

                    if "(*)" in reply:  # chatbot found some similar questions
                        suggestion = True
                    elif "#*#" in reply:  # chatbot needs clarification from user as it's not sure which subtopic is more relevant to user's question
                        confusion = True
        else:  # chatbot is not confused, but it found some similar questions to suggest user (these similar questions are all under one subtopic)
            if len(suggestion_result["questions"]) > 0:
                main_conversation_id = "choose_question_{}".format(str(uuid.uuid4()))
                if len(suggestion_result["questions"]) > 1:
                    chatbot_question = "(*)".join(
                        ["{}. {}".format(index + 1, question_answer["question_text"]) for index, question_answer in
                         enumerate(suggestion_result["questions"])][:4])
                    # chatbot_question = "{}(*){}. Talk to human".format(chatbot_question,
                    #                                                    len(suggestion_result["questions"]) + 1)

                else:
                    chatbot_question = "{}. {}(*)".format(1, suggestion_result["questions"][0]["question_text"])
                    # chatbot_question = "{}{}. Talk to human".format(chatbot_question,
                    #                                                 len(suggestion_result["questions"]) + 1)

                main_conversation_conditions = []
                for index, question_answer in enumerate(suggestion_result["questions"][:4]):
                    main_conversation_conditions.append(
                        {"user_answer": "[*]({}|{})[*]".format(index + 1,
                                                               num2word.number_to_words(index + 1)
                                                               ),
                         "chatbot_answer": question_answer["question_text"]})

                # add option for talk to human
                # main_conversation_conditions.append(
                #     {"user_answer": "[*]({}|{})[*]".format(len(suggestion_result["questions"]) + 1,
                #                                            num2word.number_to_words(
                #                                                len(suggestion_result["questions"]) + 1))
                #      "chatbot_answer": "%s {topic=%s}" % ("Talk to human", "random")
                #      })

                __add_temporary_conversational_rule(
                    topic="live_conversations",
                    annotated_user_question=nlp_controller.annotate_expression(query),
                    chatbot_question=chatbot_question,
                    main_conversation_id="random",
                    subtopic_conversation_id=main_conversation_id,
                    conditions=main_conversation_conditions
                )

                bot.load_directory(
                    os.path.join(os.path.dirname(__file__), "..", "brain/rules")
                )

                bot.sort_replies()
                reply = bot.reply(user_id, query)
                if "(*)" in reply:  # chatbot found some similar questions
                    suggestion = True
    else:
        # if user's reply is another question, it's not any of the shown options (suggested questions, subtopics)
        while reply.startswith(
                "^Return-to-Maintopic="):  # pass the question to the upper *topic(s)* in generated conversation rules
            recursive_question = reply.split("^Return-to-Maintopic=")[1]
            reply = bot.reply(user_id, recursive_question)  # ask the question again

        if reply.startswith("^Recursive="):  # reply is a chosen option
            recursive_question = reply.split("^Recursive=")[1]
            if "(*)" not in reply:
                recursive_topic = bot.get_uservar(user_id, "topic")
                bot.set_uservar(user_id, "topic", "random")
                reply = bot.reply(user_id,
                                  recursive_question)  # ask bot the question associated to the option chosen by user
                bot.set_uservar(user_id, "topic", recursive_topic)
            else:
                reply = recursive_question

        if "(*)" in reply:  # chatbot found some similar questions
            suggestion = True
        elif "#*#" in reply:  # chatbot needs clarification from user as it's not sure which subtopic is more relevant to user's question
            confusion = True

    # now, the chatbot decides what an answer to the user's question should be
    # an answer, suggested question(s), or ask for clarification about relevant subtopic(s)

    if "No Reply" in reply:  # chatbot could not understand user's question, meaning that it couldn't find any relevant subtopic nor any similar question.
        chatbot_response = "I don't know the answer of your question 🧐"

    elif confusion:  # chatbot is confused between two or more subtopics, needs to ask for clarification from user
        chatbot_response = ["Can you tell me 🤓 which of these *topic* your question is about 👇:\n\n"]
        for index, suggested_subtopic in enumerate(reply.split('#*#')[:3]):  # take only top-3 suggested subtopics
            if "{}. ".format(index + 1) in suggested_subtopic:
                # remove "1.", "2." from the suggested subtopic as we don't want "1." to be _italic_ in the shown message to user in whatsapp
                suggested_subtopic = suggested_subtopic.replace("{}. ".format(index + 1), "")

            # make the subtopic's text _italic_
            chatbot_response.append("{}. _{}_\n".format(index + 1, suggested_subtopic))
        chatbot_response = "".join(chatbot_response)  # put everything in one single sentence


    elif suggestion:  # chatbot found some similar questions, but it's not confused as those similar questions are all under one subtopic
        chatbot_response = []
        for index, suggested_question in enumerate(reply.split("(*)")[:4]):  # take only top-4 suggested questions
            if len(suggested_question.strip()) > 1:
                if "{}. ".format(index + 1) in suggested_question:
                    # remove "1.", "2." from the suggested question as we don't want "1." to be _italic_ in the shown message to user in whatsapp
                    suggested_question = suggested_question.replace("{}. ".format(index + 1), "")

                # make the question's text _italic_
                chatbot_response.append("{}. _{}_\n".format(index + 1, suggested_question.replace("\n", "")))

        if len(chatbot_response) > 1:
            chatbot_response.insert(0, "I found some similar *questions* 🤓, maybe ask any of these 👇:\n\n")
            # chatbot_response = ["I found some similar *questions* 🤓, maybe ask any of these 👇:\n\n"]
        elif len(chatbot_response) == 1:
            chatbot_response.insert(0, "I found a similar *question* 🤓, maybe ask this 👇:\n\n")
            # chatbot_response = ["I found a similar *question* 🤓, maybe ask this 👇:\n\n"]

        chatbot_response = "".join(chatbot_response)  # put everything in one single sentence

    elif reply.startswith("^User-Handover-Request"):  # user wants to talk to a human
        chatbot_response = reply.split("^User-Handover-Request=")[1]
        handover_message = [
            "Hi, a user wants to talk to you 👀\nYou can accept it by replying this 👇 message...\n\n".format(
                user_id)]
        handover_message.append("_Connect me to user {}_".format(user_id))
        handover_message = "".join(handover_message)
        handover_controller.start_handover(handover_message)
    elif reply.startswith("^User-Handover-Continue"):  # user continues talking to the human
        user_message = "*Message from user {}*:\n\"{}\"\n\nPlease reply in this 👇 format...".format(user_id, query)
        human_response_format = "HANDOVER RESPONSE\nUser: {}\n_your_message goes here..._".format(user_id)
        handover_controller.user_continue_handover(user_message, human_response_format)
    elif reply.startswith("^User-Handover-Closed"):  # user wants to end the handover and talk to the chatbot
        chatbot_response = reply.split("=")[1]
    elif reply.startswith("^Human-Handover-Accepted"):  # human accepts to talk to the user
        if user_id != human_phone_number:
            chatbot_response = "Sorry I don't have enough permission to perform this request 😥"
        else:
            chatbot_response = reply.split("=")[1]
            recipient_id = reply.split("=")[2]
            handover_controller.notify_user("Hi, you are now talking to a human 👨🏻‍💻...\nHow can I help?",
                                            recipient_id)
    elif reply.startswith("^Human-Handover-Answer"):  # human continues talking to the user
        try:
            query = query.replace("HANDOVER RESPONSE", "").strip()
            query = query.replace("User: ", "").strip()
            recipient_id = query.split("\n")[0]
            if not recipient_id.startswith("+") or not any(i.isdigit() for i in recipient_id):
                raise Exception("Issue in the format of the message returned by human!")
            chatbot_message_to_user = query.replace(recipient_id, "")
            handover_controller.notify_user(chatbot_message_to_user, recipient_id)
            chatbot_response = "Handover message:\n_{}_\nsent to user *{}*, thanks! 🙏".format(chatbot_message_to_user,
                                                                                               recipient_id)
        except Exception as split_err:
            handover_controller.notify_user(str(split_err))
            handover_controller.notify_user(
                "Your message is not in the expected format 😥, please fix it and send again.", user_id)
    elif reply.startswith("^Human-Report-Abuse"):  # human continues talking to the user
        try:
            if user_id != human_phone_number:
                chatbot_response = "Sorry I don't have enough permission to perform this request 😥"
            else:
                misbehavior_id = reply.split("=")[2]  # id of user who behaved inappropriately
                # TODO notify user that he/she is now in the blacklist
                # handover_controller.notify_user("I've received a misbehavior report about you, please explain why? 🙄",
                #                                 misbehavior_id)
                output_result = mongo_controller.add_user_to_blacklist(misbehavior_id)
                chatbot_response = reply.split("=")[1]
        except Exception as split_err:
            handover_controller.notify_user(
                "Your message is not in the expected format 😥, please fix it and send again.", user_id)
    elif any(i.isdigit() for i in
             reply):  # chatbot could match user's question with a rule, therefore it has an answer, check to see if the reply is an id of QA in mongodb
        query_result = mongo_controller.get_question_answer(reply)
        chatbot_response = [query_result["answer"]]
        answer_details = query_result["more_details"]

        if len(answer_details) > 0:
            chatbot_response.append("\n\n*More Details:* \n")
            if isinstance(answer_details, list):
                for index, link in enumerate(answer_details):
                    if link.endswith(("png", "jpg", "jpeg")):
                        chatbot_response.append("Image: _{}_\n".format(link))
                    elif "youtube" in link or link.endswith(("mkv", "mov", "mp4")):
                        chatbot_response.append("Video: _{}_\n".format(link))
                    elif link.endswith(("pdf")):
                        chatbot_response.append("PDF: _{}_\n".format(link))
                    elif link.endswith(("doc", "docx")):
                        chatbot_response.append("Document: _{}_\n".format(link))
                    else:
                        chatbot_response.append("WebPage: _{}_\n".format(link))
            elif isinstance(answer_details, str):
                if answer_details.endswith(("png", "jpg", "jpeg")):
                    chatbot_response.append("Image: _{}_\n".format(answer_details))
                elif "youtube" in answer_details or answer_details.endswith(("mkv", "mov", "mp4")):
                    chatbot_response.append("Video: _{}_\n".format(answer_details))
                elif answer_details.endswith(("pdf")):
                    chatbot_response.append("PDF: _{}_\n".format(answer_details))
                elif answer_details.endswith(("doc", "docx")):
                    chatbot_response.append("_Document: _{}_\n".format(answer_details))
                else:
                    chatbot_response.append("WebPage: _{}_\n".format(answer_details))

        chatbot_response = "".join(chatbot_response)
    else:
        chatbot_response = reply

    return chatbot_response
