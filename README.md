Installation & Usage
---------------
In order to run the chatbot locally, follow these steps:
1. Download/Run [Stanford CoreNLP server](https://stanfordnlp.github.io/CoreNLP/corenlp-server.html).
2. Install/Run [MongoDB](https://docs.mongodb.com/manual/administration/install-community/).

3. Create and activate a virtual environment:
    * `Linux`
    ```
    python -m venv env
    source ./env/bin/activate
    ```
    * `Windows`
    ```
    python -m venv env
    .\env\Scripts\activate.bat
    ```
4. Install the required packages inside the environment:
    ```
    pip install -r requirements.txt
    ```
5. Open **config.ini** configuration file and update the value of settings. 
6. Populate collection in mongoDB:
   > Note: Please make sure you fulfilled the required configs in **config.ini** file - section DEFAULT and MONGODB.
    ```
    cd scripts
    python mongodb_populate.py
    ```   

7. Run the chatbot by running the following command:
    ```
    $ python rest_app.py
    ```
    This will start the chatbot on <**host**>:<**port**> defined in config.ini file.

To use REST APIs of the chatbot, open its swagger UI from ```http://<host>:<port>/doc/``` on your browser.